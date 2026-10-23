/**
 * Document extract → markdown for MindMate (Dify).
 * Reuses doc-extract prep + site engines, outputs markdown instead of PDF download.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphShared = global.MindGraphShared;

  /**
   * @param {string} key
   * @param {string[] | string | undefined} substitutions
   * @returns {string}
   */
  function extensionUiMessage(key, substitutions) {
    const locales = global.MindGraphExtensionLocales;
    if (locales && typeof locales.message === "function") {
      return locales.message(key, substitutions);
    }
    if (typeof chrome !== "undefined" && chrome.i18n) {
      return chrome.i18n.getMessage(key, substitutions) || "";
    }
    return "";
  }
  const PDF_EXTRACT_FILES = [
    "vendor/pdfjs/pdf.worker.min.js",
    "vendor/pdfjs/pdf.min.js",
    "doc-extract/text/pdf-extract-in-tab.js",
  ];
  const PAGE_MARKDOWN_SCRIPT =
    MindGraphDocExtract.PAGE_CONTENT_INJECT_SCRIPT || "doc-extract/text/page-content.js";
  const DEFAULT_MAX_MARKDOWN_CHARS = MindGraphShared.DEFAULT_MINDMATE_CAPTURE_CHARS;
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
   * @param {{ suppressMindMateUi?: boolean }} [options]
   * @returns {boolean}
   */
  function shouldTrackMindMateUi(options) {
    return !(options && options.suppressMindMateUi);
  }

  /**
   * @param {{ pageUrl: string, hostId: string, captureOptions?: { suppressMindMateUi?: boolean } }} ctx
   * @param {{ ok: boolean, error?: string, source?: string, markdown?: string, fromSelection?: boolean, title?: string, url?: string, assetTotal?: number }} result
   * @returns {Promise<object>}
   */
  async function finalizeCaptureResult(ctx, result) {
    const trackUi = shouldTrackMindMateUi(ctx.captureOptions);
    const dbg = trackUi ? captureDebug() : null;
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
    const prog = trackUi ? captureProgress() : null;
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
          globalThis.__MGPageContent &&
          typeof globalThis.__MGPageContent.truncateMarkdown === "function"
            ? globalThis.__MGPageContent.truncateMarkdown(text, limit)
            : globalThis.__MGMindMatePageMarkdown &&
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
        const api = globalThis.__MGPageContent || globalThis.__MGMindMatePageMarkdown;
        if (api && typeof api.extractPageMarkdownAsync === "function") {
          return api.extractPageMarkdownAsync(limit, {
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
      let text = await MindGraphDocExtract.extractPdfBlobTextOffscreen(blob, PDF_MAX_PAGES, maxChars);
      text = typeof text === "string" ? text.trim() : "";
      const pdfTitle =
        (tabTitle && tabTitle.replace(/\.pdf$/i, "").trim()) ||
        (MindGraphDocExtract.titleFromBrowserPdfUrl
          ? MindGraphDocExtract.titleFromBrowserPdfUrl(pageUrl)
          : "PDF document");
      if (typeof MindGraphDocExtract.finishPdfBlobText === "function") {
        text = (await MindGraphDocExtract.finishPdfBlobText(tabId, blob, text, 8, maxChars, pdfTitle)).trim();
      }
      if (!text || text.length < 20) {
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
      let text = await extractFn(tabId, blob, limits.pdfMaxPages, maxChars);
      const title = resolved.title || "cnki-document";
      if (typeof MindGraphDocExtract.finishPdfBlobText === "function") {
        text = await MindGraphDocExtract.finishPdfBlobText(
          tabId,
          blob,
          text,
          limits.pdfMaxPages,
          maxChars,
          title,
        );
      }
      if (text.length < 80) {
        return { ok: false, error: "CNKI_PDF_URL_MISS" };
      }
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
      let text = await extractFn(tabId, blob, limits.pdfMaxPages, maxChars);
      let title = "wenku-document";
      try {
        title = decodeURIComponent(new URL(pageUrl).pathname.split("/").pop() || title);
      } catch {
        /* keep default */
      }
      if (typeof MindGraphDocExtract.finishPdfBlobText === "function") {
        text = await MindGraphDocExtract.finishPdfBlobText(
          tabId,
          blob,
          text,
          limits.pdfMaxPages,
          maxChars,
          title,
        );
      }
      if (text.length < 80) {
        return null;
      }
      let markdown = formatDocumentMarkdown(title, text, pageUrl, maxChars);
      if (
        limits.previewNotice &&
        MindGraphDocExtract.prependCaptureNotice &&
        typeof chrome !== "undefined" &&
        chrome.i18n
      ) {
        const notice = extensionUiMessage(limits.previewNotice, [String(limits.pdfMaxPages)]);
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
    const notice = extensionUiMessage(limits.previewNotice);
    if (!notice) {
      return markdown;
    }
    return MindGraphDocExtract.prependCaptureNotice(markdown, notice, maxChars);
  }

  /**
   * @param {number} tabId
   * @param {Blob} blob
   * @param {string} title
   * @param {string} url
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function pdfBlobToDocumentMarkdown(tabId, blob, title, url, maxChars) {
    let text = await extractPdfBlobTextWithFallback(tabId, blob, PDF_MAX_PAGES, maxChars);
    if (typeof MindGraphDocExtract.finishPdfBlobText === "function") {
      text = await MindGraphDocExtract.finishPdfBlobText(tabId, blob, text, 8, maxChars, title);
    }
    if (!text || text.trim().length < 80) {
      return "";
    }
    return formatDocumentMarkdown(title, text.trim(), url, maxChars);
  }

  /**
   * @param {number} tabId
   * @param {number} [maxMarkdownChars]
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string, suppressMindMateUi?: boolean }} [options]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection: boolean, source?: string } | { ok: false, error: string }>}
   */
  async function runDocumentExtractToMarkdown(tabId, maxMarkdownChars, options) {
    const captureOptions = options && typeof options === "object" ? options : {};
    /** @type {{ pageUrl: string, hostId: string, captureOptions: typeof captureOptions }} */
    const ctx = { pageUrl: "", hostId: "generic", captureOptions };
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

      const prog = shouldTrackMindMateUi(captureOptions) ? captureProgress() : null;
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
          hasSmarteduToken: Boolean(captureOptions.smarteduToken),
        });
      }

      if (typeof MindGraphDocExtract.runProductRuleCapture !== "function") {
        return finalizeCaptureResult(ctx, { ok: false, error: "errMindMatePageCaptureFailed" });
      }
      const captureApi = {
        captureDebug,
        tryBrowserPdfTabMarkdown,
        captureSelectionMarkdown,
        collectInPageMarkdown,
        extractEmbeddedPdfTextFromTab,
        tryCnkiReaderTextMarkdown,
        tryCnkiPdfMarkdown,
        tryWenkuPdfMarkdown,
        tryDomArticleMarkdown,
        runPrepOnTab: MindGraphDocExtract.runPrepOnTab,
        formatDocumentMarkdown,
        applyHostPreviewNotice,
        pdfBlobToDocumentMarkdown,
      };
      return MindGraphDocExtract.runProductRuleCapture(captureApi, {
        ctx,
        tabId,
        tab,
        pageUrl,
        hostEntry,
        fileFirst,
        maxChars,
        options: options || {},
        isKnownHost,
        finalizeCaptureResult,
      });
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
