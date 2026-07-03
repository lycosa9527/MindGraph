/**
 * Document extract → markdown for MindMate (Dify).
 * Reuses doc-extract prep + site engines, outputs markdown instead of PDF download.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphShared = global.MindGraphShared;
  const PDF_EXTRACT_FILES = ["vendor/pdfjs/pdf.min.js", "doc-extract/text/pdf-extract-in-tab.js"];
  const PAGE_MARKDOWN_SCRIPT = "mindmate-page-markdown.js";
  const DEFAULT_MAX_MARKDOWN_CHARS = 8000;
  const PDF_MAX_PAGES = 120;

  /**
   * @returns {{ beginCapture: Function, log: Function, finishCapture: Function } | null}
   */
  function captureDebug() {
    const root = global.MindGraphMindMate;
    return root && root.captureDebug ? root.captureDebug : null;
  }

  /**
   * @returns {{ beginCaptureProgress: Function, finishCaptureProgress: Function } | null}
   */
  function captureProgress() {
    const root = global.MindGraphMindMate;
    return root && root.captureProgress ? root.captureProgress : null;
  }

  /**
   * @param {{ pageUrl: string, hostId: string }} ctx
   * @param {{ ok: boolean, error?: string, source?: string, markdown?: string, fromSelection?: boolean, title?: string, url?: string, assetTotal?: number }} result
   * @returns {Promise<object>}
   */
  async function finalizeCaptureResult(ctx, result) {
    const dbg = captureDebug();
    if (dbg) {
      await dbg.finishCapture({
        pageUrl: ctx.pageUrl,
        hostId: ctx.hostId,
        ok: Boolean(result.ok),
        error: result.error || "",
        source: result.source || "",
        markdownLen: result.markdown ? result.markdown.length : 0,
        fromSelection: Boolean(result.fromSelection),
      });
    }
    const prog = captureProgress();
    if (prog) {
      if (result.ok) {
        await prog.finishCaptureProgress({
          ok: true,
          hostId: ctx.hostId,
          pageUrl: ctx.pageUrl,
          source: result.source || "",
          title: result.title || "",
          markdownLen: result.markdown ? result.markdown.length : 0,
          fromSelection: Boolean(result.fromSelection),
          assetTotal: result.assetTotal || 0,
        });
      } else {
        await prog.finishCaptureProgress({
          ok: false,
          hostId: ctx.hostId,
          pageUrl: ctx.pageUrl,
          error: result.error || "errMindMatePageEmpty",
        });
      }
    }
    if (result.ok && !result.hostId) {
      return { ...result, hostId: ctx.hostId };
    }
    return result;
  }

  /**
   * @param {string} title
   * @param {string} body
   * @param {string} url
   * @param {number} maxChars
   * @returns {string}
   */
  function formatDocumentMarkdown(title, body, url, maxChars) {
    const safeTitle = (title || "document").trim();
    const safeUrl = (url || "").trim();
    const header = `# ${safeTitle}\n\n> ${safeUrl}\n\n`;
    const content = (body || "").trim();
    const combined = header + content;
    if (!maxChars || combined.length <= maxChars) {
      return combined;
    }
    const budget = Math.max(0, maxChars - header.length - 10);
    if (budget <= 0) {
      return `${header.trim()}\n\n…`.slice(0, maxChars);
    }
    const trimmed = content.slice(0, budget).trim();
    return `${header}${trimmed}\n\n…`;
  }

  /**
   * @param {number} tabId
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, fromSelection: boolean, source?: string } | null>}
   */
  async function captureSelectionMarkdown(tabId, maxChars) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [PAGE_MARKDOWN_SCRIPT],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (limit) => {
        const selection = window.getSelection();
        if (!selection || !selection.toString().trim()) {
          return null;
        }
        const title = document.title || "";
        const url = location.href || "";
        const text = selection.toString().trim();
        const markdown =
          globalThis.__MGMindMatePageMarkdown &&
          typeof globalThis.__MGMindMatePageMarkdown.truncateMarkdown === "function"
            ? globalThis.__MGMindMatePageMarkdown.truncateMarkdown(text, limit)
            : text.slice(0, limit);
        return { title, url, markdown, fromSelection: true, source: "selection" };
      },
      args: [maxChars],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || !payload.markdown) {
      return null;
    }
    return payload;
  }

  /**
   * @param {number} tabId
   * @param {number} maxChars
   * @param {string} pageUrl
   * @param {string} tabTitle
   * @param {{ skipSelection?: boolean }} [options]
   * @returns {Promise<{ title: string, url: string, markdown: string, fromSelection: boolean, source: string }>}
   */
  async function collectInPageMarkdown(tabId, maxChars, pageUrl, tabTitle, options) {
    const skipSelection = Boolean(options && options.skipSelection);
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [PAGE_MARKDOWN_SCRIPT],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async (limit, skipSel) => {
        if (
          globalThis.__MGMindMatePageMarkdown &&
          typeof globalThis.__MGMindMatePageMarkdown.extractPageMarkdownAsync === "function"
        ) {
          return globalThis.__MGMindMatePageMarkdown.extractPageMarkdownAsync(limit, {
            skipSelection: skipSel,
          });
        }
        return { title: document.title || "", url: location.href || "", markdown: "", fromSelection: false };
      },
      args: [maxChars, skipSelection],
    });
    const payload = results && results[0] && results[0].result;
    const markdown = payload && typeof payload.markdown === "string" ? payload.markdown.trim() : "";
    return {
      title: (payload && payload.title) || tabTitle || "",
      url: (payload && payload.url) || pageUrl,
      markdown,
      fromSelection: Boolean(payload && payload.fromSelection),
      source: (payload && payload.source) || "page-markdown",
    };
  }

  /**
   * @param {number} tabId
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractEmbeddedPdfTextFromTab(tabId, maxPages, maxChars) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/text/pdf-extract-in-tab.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async (pages, chars) => {
        if (
          !globalThis.__MGDocExtractPdf ||
          typeof globalThis.__MGDocExtractPdf.extractEmbeddedPdfViewerText !== "function"
        ) {
          return "";
        }
        return globalThis.__MGDocExtractPdf.extractEmbeddedPdfViewerText(pages, chars);
      },
      args: [maxPages, maxChars],
    });
    const text = results && results[0] && results[0].result;
    return typeof text === "string" ? text.trim() : "";
  }

  /**
   * @param {number} tabId
   * @param {string} pageUrl
   * @param {string} tabTitle
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | null>}
   */
  async function tryBrowserPdfTabMarkdown(tabId, pageUrl, tabTitle, maxChars) {
    if (
      !MindGraphShared ||
      typeof MindGraphShared.isBrowserPdfTabUrl !== "function" ||
      !MindGraphShared.isBrowserPdfTabUrl(pageUrl)
    ) {
      return null;
    }
    if (
      typeof MindGraphDocExtract.fetchPdfBlobFromBrowserTabUrl !== "function" ||
      typeof MindGraphDocExtract.extractPdfBlobTextOffscreen !== "function"
    ) {
      return null;
    }
    const blob = await MindGraphDocExtract.fetchPdfBlobFromBrowserTabUrl(pageUrl);
    if (!blob) {
      return null;
    }
    try {
      const text = await MindGraphDocExtract.extractPdfBlobTextOffscreen(blob, PDF_MAX_PAGES, maxChars);
      if (!text || text.trim().length < 20) {
        return null;
      }
      const title =
        (tabTitle && tabTitle.replace(/\.pdf$/i, "").trim()) ||
        (MindGraphDocExtract.titleFromBrowserPdfUrl
          ? MindGraphDocExtract.titleFromBrowserPdfUrl(pageUrl)
          : "PDF document");
      return {
        title,
        url: pageUrl,
        markdown: formatDocumentMarkdown(title, text.trim(), pageUrl, maxChars),
        source: "browser-pdf",
      };
    } catch {
      return null;
    }
  }

  /**
   * @param {number} tabId
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  /**
   * @param {ArrayBuffer} buffer
   * @returns {string}
   */
  function pdfBufferToBase64Arg(buffer) {
    if (
      typeof MindGraphOffscreenBlobs !== "undefined" &&
      MindGraphOffscreenBlobs &&
      typeof MindGraphOffscreenBlobs.arrayBufferToBase64 === "function"
    ) {
      return MindGraphOffscreenBlobs.arrayBufferToBase64(buffer);
    }
    const bytes = new Uint8Array(buffer);
    const chunkSize = 8192;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  async function extractPdfBlobTextInTab(tabId, blob, maxPages, maxChars) {
    const buffer = await blob.arrayBuffer();
    if (!buffer || buffer.byteLength < 64) {
      return "";
    }
    const base64 = pdfBufferToBase64Arg(buffer);
    await chrome.scripting.executeScript({
      target: { tabId },
      files: PDF_EXTRACT_FILES,
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async (pdfBase64, pages, chars) => {
        if (
          !globalThis.__MGDocExtractPdf ||
          typeof globalThis.__MGDocExtractPdf.extractTextFromPdfBuffer !== "function"
        ) {
          throw new Error("PDFJS_NOT_LOADED");
        }
        const binaryStr = atob(pdfBase64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i += 1) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        return globalThis.__MGDocExtractPdf.extractTextFromPdfBuffer(bytes.buffer, pages, chars);
      },
      args: [base64, maxPages, maxChars],
    });
    const text = results && results[0] && results[0].result;
    return typeof text === "string" ? text.trim() : "";
  }

  /**
   * Prefer offscreen pdf.js when tab scripting is unavailable (browser PDF viewer).
   * @param {number} tabId
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractPdfBlobTextWithFallback(tabId, blob, maxPages, maxChars) {
    if (typeof MindGraphDocExtract.extractPdfBlobTextOffscreen === "function") {
      try {
        const offscreenText = await MindGraphDocExtract.extractPdfBlobTextOffscreen(
          blob,
          maxPages,
          maxChars,
        );
        if (offscreenText && offscreenText.trim().length >= 20) {
          return offscreenText.trim();
        }
      } catch {
        /* fall through to tab injection */
      }
    }
    return extractPdfBlobTextInTab(tabId, blob, maxPages, maxChars);
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | null>}
   */
  async function tryCnkiReaderTextMarkdown(tabId, hostEntry, pageUrl, maxChars) {
    if (
      hostEntry.id !== "cnki" ||
      typeof MindGraphDocExtract.collectCnkiReaderTextFromTab !== "function" ||
      typeof MindGraphDocExtract.parseCnkiPageUrl !== "function"
    ) {
      return null;
    }
    const parsed = MindGraphDocExtract.parseCnkiPageUrl(pageUrl);
    if (!parsed || (parsed.kind !== "flowpdf" && parsed.kind !== "trial-read" && parsed.kind !== "reader")) {
      return null;
    }
    const limits = MindGraphDocExtract.markdownLimitsForHost
      ? MindGraphDocExtract.markdownLimitsForHost(hostEntry)
      : { pdfMaxPages: PDF_MAX_PAGES, previewNotice: null };
    try {
      const payload = await MindGraphDocExtract.collectCnkiReaderTextFromTab(
        tabId,
        hostEntry,
        limits.pdfMaxPages,
        maxChars,
      );
      if (!payload.text || payload.text.trim().length < 80) {
        return null;
      }
      const title = payload.title || "cnki-document";
      return {
        title,
        url: pageUrl,
        markdown: formatDocumentMarkdown(title, payload.text.trim(), pageUrl, maxChars),
        source: "cnki-reader-text",
      };
    } catch {
      return null;
    }
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | { ok: false, error: string } | null>}
   */
  async function tryCnkiPdfMarkdown(tabId, hostEntry, pageUrl, maxChars) {
    if (hostEntry.id !== "cnki" || typeof MindGraphDocExtract.resolveCnkiPdfFromTab !== "function") {
      return null;
    }
    const limits = MindGraphDocExtract.markdownLimitsForHost
      ? MindGraphDocExtract.markdownLimitsForHost(hostEntry)
      : { pdfMaxPages: PDF_MAX_PAGES, previewNotice: null };
    let resolved = null;
    try {
      resolved = await MindGraphDocExtract.resolveCnkiPdfFromTab(tabId);
    } catch {
      return { ok: false, error: "CNKI_PDF_URL_MISS" };
    }
    if (!resolved) {
      return { ok: false, error: "CNKI_PDF_URL_MISS" };
    }
    if (resolved.error === "CNKI_CAPTCHA" || resolved.error === "CNKI_LOGIN_REQUIRED") {
      return { ok: false, error: resolved.error };
    }
    const candidates =
      typeof MindGraphDocExtract.mergeCnkiDownloadCandidates === "function"
        ? MindGraphDocExtract.mergeCnkiDownloadCandidates(resolved, pageUrl)
        : [];
    if (!candidates.length) {
      return { ok: false, error: resolved.error || "CNKI_PDF_URL_MISS" };
    }
    try {
      let blob = null;
      if (typeof MindGraphDocExtract.fetchCnkiPdfBlobInTab === "function") {
        blob = await MindGraphDocExtract.fetchCnkiPdfBlobInTab(tabId, candidates);
      }
      if (!blob && typeof MindGraphDocExtract.fetchCnkiPdfCandidates === "function") {
        blob = await MindGraphDocExtract.fetchCnkiPdfCandidates({ ...resolved, guessUrls: candidates });
      }
      if (!blob) {
        return { ok: false, error: "CNKI_PDF_URL_MISS" };
      }
      const extractFn =
        typeof MindGraphDocExtract.extractBlobTextInTab === "function"
          ? MindGraphDocExtract.extractBlobTextInTab
          : extractPdfBlobTextWithFallback;
      const text = await extractFn(tabId, blob, limits.pdfMaxPages, maxChars);
      if (text.length < 80) {
        return { ok: false, error: "CNKI_PDF_URL_MISS" };
      }
      const title = resolved.title || "cnki-document";
      return {
        title,
        url: pageUrl,
        markdown: formatDocumentMarkdown(title, text, pageUrl, maxChars),
        source: "cnki-pdf",
      };
    } catch (err) {
      const message = err instanceof Error ? err.message : "CNKI_PDF_URL_MISS";
      return { ok: false, error: message };
    }
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | null>}
   */
  async function tryWenkuPdfMarkdown(tabId, hostEntry, pageUrl, maxChars) {
    if (hostEntry.id !== "wenku" || typeof MindGraphDocExtract.guessWenkuReaderPdfUrl !== "function") {
      return null;
    }
    const limits = MindGraphDocExtract.markdownLimitsForHost
      ? MindGraphDocExtract.markdownLimitsForHost(hostEntry)
      : { pdfMaxPages: PDF_MAX_PAGES, previewNotice: null };
    const directUrl = MindGraphDocExtract.guessWenkuReaderPdfUrl(pageUrl);
    if (!directUrl) {
      return null;
    }
    try {
      const res = await fetch(directUrl, { method: "GET" });
      if (!res.ok) {
        return null;
      }
      const blob = await res.blob();
      const extractFn =
        typeof MindGraphDocExtract.extractBlobTextInTab === "function"
          ? MindGraphDocExtract.extractBlobTextInTab
          : extractPdfBlobTextWithFallback;
      const text = await extractFn(tabId, blob, limits.pdfMaxPages, maxChars);
      if (text.length < 80) {
        return null;
      }
      let title = "wenku-document";
      try {
        title = decodeURIComponent(new URL(pageUrl).pathname.split("/").pop() || title);
      } catch {
        /* keep default */
      }
      let markdown = formatDocumentMarkdown(title, text, pageUrl, maxChars);
      if (
        limits.previewNotice &&
        MindGraphDocExtract.prependCaptureNotice &&
        typeof chrome !== "undefined" &&
        chrome.i18n
      ) {
        const notice = chrome.i18n.getMessage(limits.previewNotice, [String(limits.pdfMaxPages)]);
        markdown = MindGraphDocExtract.prependCaptureNotice(markdown, notice, maxChars);
      }
      return {
        title,
        url: pageUrl,
        markdown,
        source: "wenku-pdf",
      };
    } catch {
      return null;
    }
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {number} maxChars
   * @param {string} pageUrl
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | null>}
   */
  async function tryDomArticleMarkdown(tabId, hostEntry, maxChars, pageUrl) {
    if (typeof MindGraphDocExtract.collectDomArticleFromTab !== "function") {
      return null;
    }
    const useDomEngine = hostEntry.engine === "dom-article";
    const useCanvasFallback =
      MindGraphDocExtract.isCanvasRenderHost &&
      MindGraphDocExtract.isCanvasRenderHost(hostEntry);
    if (!useDomEngine && !useCanvasFallback) {
      return null;
    }
    const collectHost = useDomEngine
      ? hostEntry
      : {
          ...hostEntry,
          pageSelectors: hostEntry.pageSelectors || [
            "main",
            "article",
            "[role='main']",
            ".reader",
            ".doc-reader",
            ".doc-content",
            "body",
          ],
        };
    try {
      const payload = await MindGraphDocExtract.collectDomArticleFromTab(tabId, collectHost);
      let body = (payload.text || "").trim();
      if (body.length < 40 && payload.html && MindGraphDocExtract.stripHtmlToPlainText) {
        body = MindGraphDocExtract.stripHtmlToPlainText(payload.html);
      }
      if (body.length < 40) {
        return null;
      }
      const title = payload.title || hostEntry.label || "article";
      return {
        title,
        url: pageUrl,
        markdown: formatDocumentMarkdown(title, body, pageUrl, maxChars),
        source: useDomEngine ? "dom-article" : "dom-fallback",
      };
    } catch {
      return null;
    }
  }

  /**
   * @param {string} markdown
   * @param {object} hostEntry
   * @param {number} maxChars
   * @returns {string}
   */
  function applyHostPreviewNotice(markdown, hostEntry, maxChars) {
    if (
      !MindGraphDocExtract.markdownLimitsForHost ||
      !MindGraphDocExtract.prependCaptureNotice ||
      typeof chrome === "undefined" ||
      !chrome.i18n
    ) {
      return markdown;
    }
    const limits = MindGraphDocExtract.markdownLimitsForHost(hostEntry);
    if (!limits.previewNotice || hostEntry.id === "wenku") {
      return markdown;
    }
    const notice = chrome.i18n.getMessage(limits.previewNotice);
    if (!notice) {
      return markdown;
    }
    return MindGraphDocExtract.prependCaptureNotice(markdown, notice, maxChars);
  }

  /**
   * @param {number} tabId
   * @param {number} [maxMarkdownChars]
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection: boolean, source?: string } | { ok: false, error: string }>}
   */
  async function runDocumentExtractToMarkdown(tabId, maxMarkdownChars, options) {
    /** @type {{ pageUrl: string, hostId: string }} */
    const ctx = { pageUrl: "", hostId: "generic" };
    const dbg = captureDebug();

    if (!tabId || tabId < 1) {
      if (dbg) {
        dbg.log("validate", "invalid tabId", { tabId });
      }
      return finalizeCaptureResult(ctx, { ok: false, error: "errMindMatePageCaptureFailed" });
    }
    const maxChars =
      typeof maxMarkdownChars === "number" && maxMarkdownChars > 0
        ? maxMarkdownChars
        : DEFAULT_MAX_MARKDOWN_CHARS;

    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      ctx.pageUrl = pageUrl;
      if (MindGraphShared && MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        if (dbg) {
          dbg.beginCapture({ tabId, pageUrl, hostId: "restricted" });
          dbg.log("validate", "restricted tab URL");
        }
        return finalizeCaptureResult(ctx, { ok: false, error: "errRestrictedPage" });
      }

      const hostEntry = MindGraphDocExtract.matchHost(pageUrl);
      ctx.hostId = hostEntry.id;
      const isKnownHost = hostEntry.id !== "generic";
      const fileFirst =
        typeof MindGraphDocExtract.hostRequiresFileExtract === "function" &&
        MindGraphDocExtract.hostRequiresFileExtract(hostEntry);

      const prog = captureProgress();
      if (prog) {
        await prog.beginCaptureProgress({ hostId: hostEntry.id, pageUrl, tabId });
        if (fileFirst && hostEntry.id === "smartedu") {
          await prog.publishCaptureProgress({
            phase: "reading",
            messageKey: "mindmatePageContextSmarteduStarting",
            messageSubs: [],
          });
        } else if (fileFirst) {
          await prog.publishCaptureProgress({
            phase: "reading",
            messageKey: "mindmatePageContextHostExtract",
            messageSubs: [hostEntry.label || hostEntry.id],
          });
        }
      }

      if (dbg) {
        dbg.beginCapture({ tabId, pageUrl, hostId: hostEntry.id, fileFirst });
        dbg.log("host", isKnownHost ? `known host ${hostEntry.id}` : "generic host", {
          engine: hostEntry.engine,
          fileFirst,
          maxChars,
          hasSmarteduToken: Boolean(options && options.smarteduToken),
        });
      }

      const autoScanGeneric = hostEntry.id === "generic";
      if (!fileFirst && !autoScanGeneric) {
        const selectionPayload = await captureSelectionMarkdown(tabId, maxChars);
        if (selectionPayload && selectionPayload.markdown) {
          if (dbg) {
            dbg.log("selection", "using text selection", {
              markdownLen: selectionPayload.markdown.length,
            });
          }
          return finalizeCaptureResult(ctx, {
            ok: true,
            title: selectionPayload.title,
            url: selectionPayload.url,
            markdown: selectionPayload.markdown,
            fromSelection: true,
            source: selectionPayload.source,
          });
        }
        if (dbg) {
          dbg.log("selection", "no selection text");
        }
      } else if (dbg) {
        dbg.log(
          "selection",
          autoScanGeneric ? "skipped for generic auto-scan" : "skipped for file-first host",
        );
      }

      const browserPdf = await tryBrowserPdfTabMarkdown(
        tabId,
        pageUrl,
        tab.title || "",
        maxChars,
      );
      if (browserPdf && browserPdf.markdown) {
        if (dbg) {
          dbg.log("browser-pdf", "extracted tab PDF", { markdownLen: browserPdf.markdown.length });
        }
        return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...browserPdf });
      }
      if (dbg) {
        dbg.log("browser-pdf", "not a browser PDF tab or empty");
      }

      if (hostEntry.id === "smartedu" && typeof MindGraphDocExtract.trySmartEduPdfMarkdown === "function") {
        if (dbg) {
          dbg.log("smartedu", "starting SmartEdu PDF pipeline");
        }
        const smarteduResult = await MindGraphDocExtract.trySmartEduPdfMarkdown(
          tabId,
          pageUrl,
          maxChars,
          options || {},
        );
        if (smarteduResult && smarteduResult.ok === false) {
          if (dbg) {
            dbg.log("smartedu", "SmartEdu pipeline error", { error: smarteduResult.error });
          }
          return finalizeCaptureResult(ctx, smarteduResult);
        }
        if (smarteduResult && smarteduResult.markdown) {
          if (dbg) {
            dbg.log("smartedu", "SmartEdu markdown ready", {
              markdownLen: smarteduResult.markdown.length,
              source: smarteduResult.source,
            });
          }
          return finalizeCaptureResult(ctx, {
            ok: true,
            title: smarteduResult.title,
            url: smarteduResult.url,
            markdown: smarteduResult.markdown,
            fromSelection: false,
            source: smarteduResult.source,
            assetTotal: smarteduResult.assetTotal || 0,
          });
        }
        if (dbg) {
          dbg.log("smartedu", "SmartEdu returned no markdown", { error: "errExtractWrongPage" });
        }
        return finalizeCaptureResult(ctx, { ok: false, error: "errExtractWrongPage" });
      }

      if (isKnownHost && typeof MindGraphDocExtract.runPrepOnTab === "function") {
        if (dbg) {
          dbg.log("prep", `runPrepOnTab for ${hostEntry.id}`);
        }
        await MindGraphDocExtract.runPrepOnTab(tabId, hostEntry, () => {});
      }

      if (isKnownHost) {
        const embeddedText = await extractEmbeddedPdfTextFromTab(tabId, PDF_MAX_PAGES, maxChars);
        if (dbg) {
          dbg.log("embedded-pdf", "embedded PDF text layer", { chars: embeddedText.length });
        }
        if (embeddedText.length >= 80) {
          const title = tab.title || hostEntry.label || "document";
          return finalizeCaptureResult(ctx, {
            ok: true,
            title,
            url: pageUrl,
            markdown: formatDocumentMarkdown(title, embeddedText, pageUrl, maxChars),
            fromSelection: false,
            source: "page-pdfjs",
          });
        }

        /** @type {string | null} */
        let cnkiLastError = null;

        if (hostEntry.id === "cnki") {
          const cnkiReaderText = await tryCnkiReaderTextMarkdown(tabId, hostEntry, pageUrl, maxChars);
          if (cnkiReaderText && cnkiReaderText.markdown) {
            if (dbg) {
              dbg.log("cnki-reader", "CNKI reader text extracted", {
                markdownLen: cnkiReaderText.markdown.length,
              });
            }
            return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...cnkiReaderText });
          }
          if (dbg) {
            dbg.log("cnki-reader", "CNKI reader text path failed or empty");
          }
        }

        const cnkiPdf = await tryCnkiPdfMarkdown(tabId, hostEntry, pageUrl, maxChars);
        if (cnkiPdf && cnkiPdf.markdown) {
          if (dbg) {
            dbg.log("cnki-pdf", "CNKI PDF extracted", { markdownLen: cnkiPdf.markdown.length });
          }
          return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...cnkiPdf });
        }
        if (cnkiPdf && cnkiPdf.ok === false && cnkiPdf.error) {
          cnkiLastError = cnkiPdf.error;
        }
        if (dbg && hostEntry.id === "cnki") {
          dbg.log("cnki-pdf", "CNKI PDF path failed or empty", { error: cnkiLastError || "" });
        }

        const wenkuPdf = await tryWenkuPdfMarkdown(tabId, hostEntry, pageUrl, maxChars);
        if (wenkuPdf && wenkuPdf.markdown) {
          if (dbg) {
            dbg.log("wenku-pdf", "Wenku PDF extracted", { markdownLen: wenkuPdf.markdown.length });
          }
          return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...wenkuPdf });
        }
        if (dbg && hostEntry.id === "wenku") {
          dbg.log("wenku-pdf", "Wenku PDF path failed or empty");
        }

        if (!fileFirst) {
          const domArticle = await tryDomArticleMarkdown(tabId, hostEntry, maxChars, pageUrl);
          if (domArticle && domArticle.markdown) {
            if (dbg) {
              dbg.log("dom-article", "DOM article extracted", {
                markdownLen: domArticle.markdown.length,
                source: domArticle.source,
              });
            }
            domArticle.markdown = applyHostPreviewNotice(domArticle.markdown, hostEntry, maxChars);
            return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...domArticle });
          }
          if (dbg) {
            dbg.log("dom-article", "DOM article empty or too short");
          }
        } else if (dbg) {
          dbg.log("dom-article", "skipped DOM fallback for file-first host");
        }

        if (fileFirst) {
          let fileFirstError = "errMindMatePageEmpty";
          if (hostEntry.id === "cnki") {
            const loginLike =
              cnkiLastError === "CNKI_LOGIN_REQUIRED" ||
              cnkiLastError === "CNKI_CAPTCHA" ||
              /BINARY_HTTP_401|BINARY_HTTP_403|LOGIN/i.test(cnkiLastError || "");
            if (
              loginLike &&
              typeof MindGraphDocExtract.resolveExtractErrorKey === "function"
            ) {
              fileFirstError = MindGraphDocExtract.resolveExtractErrorKey(cnkiLastError, hostEntry);
            }
          } else if (hostEntry.id === "wenku") {
            fileFirstError = "errExtractWenkuNoPreview";
          }
          if (dbg) {
            dbg.log("file-first", "all file extract paths failed", { error: fileFirstError });
          }
          return finalizeCaptureResult(ctx, { ok: false, error: fileFirstError });
        }
      }

      const pagePayload = await collectInPageMarkdown(
        tabId,
        maxChars,
        pageUrl,
        tab.title || "",
        { skipSelection: autoScanGeneric },
      );
      if (pagePayload.markdown) {
        if (dbg) {
          dbg.log("page-markdown", "generic page markdown", {
            markdownLen: pagePayload.markdown.length,
            source: pagePayload.source,
          });
        }
        pagePayload.markdown = applyHostPreviewNotice(pagePayload.markdown, hostEntry, maxChars);
        return finalizeCaptureResult(ctx, {
          ok: true,
          title: pagePayload.title,
          url: pagePayload.url,
          markdown: pagePayload.markdown,
          fromSelection: false,
          source: pagePayload.source,
        });
      }
      if (dbg) {
        dbg.log("page-markdown", "generic page markdown empty");
      }

      if (
        MindGraphDocExtract.isCanvasRenderHost &&
        MindGraphDocExtract.isCanvasRenderHost(hostEntry)
      ) {
        const canvasCount = MindGraphDocExtract.countCanvasPagesInTab
          ? await MindGraphDocExtract.countCanvasPagesInTab(tabId, hostEntry)
          : null;
        if (dbg) {
          dbg.log("canvas", "canvas host with no text", { canvasCount });
        }
        if (canvasCount && canvasCount > 0) {
          return finalizeCaptureResult(ctx, { ok: false, error: "errMindMateCanvasPreviewEmpty" });
        }
      }

      if (dbg) {
        dbg.log("finish", "no capture path produced markdown", { error: "errMindMatePageEmpty" });
      }
      return finalizeCaptureResult(ctx, { ok: false, error: "errMindMatePageEmpty" });
    } catch (err) {
      if (dbg) {
        dbg.log("exception", err instanceof Error ? err.message : "capture exception", {
          name: err instanceof Error ? err.name : "Error",
        });
      }
      return finalizeCaptureResult(ctx, { ok: false, error: "errMindMatePageCaptureFailed" });
    }
  }

  MindGraphDocExtract.formatDocumentMarkdown = formatDocumentMarkdown;
  MindGraphDocExtract.extractPdfBlobTextInTab = extractPdfBlobTextInTab;
  MindGraphDocExtract.extractPdfBlobTextWithFallback = extractPdfBlobTextWithFallback;
  MindGraphDocExtract.runDocumentExtractToMarkdown = runDocumentExtractToMarkdown;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
