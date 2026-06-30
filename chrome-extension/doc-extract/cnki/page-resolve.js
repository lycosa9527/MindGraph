/**
 * Page-context CNKI PDF download URL resolver (detail + flowpdf reader).
 * Ported patterns from CNKI PDF RIS Helper (GreasyFork 425133) and cnki-download skill.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractCnki = global.__MGDocExtractCnki || {};

  /**
   * @returns {boolean}
   */
  function hasVisibleCaptcha() {
    const cap = document.querySelector("#tcaptcha_transform_dy");
    if (!cap) {
      return false;
    }
    const rect = cap.getBoundingClientRect();
    return rect.top >= 0 && rect.width > 0 && rect.height > 0;
  }

  /**
   * @returns {boolean}
   */
  function looksNotLoggedIn() {
    const notLogged = document.querySelector(".downloadlink.icon-notlogged");
    if (!notLogged) {
      return false;
    }
    const rect = notLogged.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  /**
   * @returns {string}
   */
  function readDocumentTitle() {
    const fromBrief = document.querySelector(".brief h1");
    if (fromBrief && fromBrief.textContent) {
      return fromBrief.textContent.trim().replace(/\s*网络首发\s*$/, "");
    }
    const fromReader = document.querySelector(".reader-title, .doc-title, h1.title, .title h1");
    if (fromReader && fromReader.textContent) {
      return fromReader.textContent.trim();
    }
    return (document.title || "cnki-document").replace(/\s*-\s*中国知网.*$/i, "").trim();
  }

  /**
   * @param {string} href
   * @returns {string | null}
   */
  function normalizePdfHref(href) {
    const raw = (href || "").trim();
    if (!raw || raw === "#" || raw.startsWith("javascript:")) {
      return null;
    }
    let absolute = raw;
    if (raw.startsWith("//")) {
      absolute = `${window.location.protocol}${raw}`;
    } else if (raw.startsWith("/")) {
      absolute = `${window.location.origin}${raw}`;
    }
    if (!/pdf|caj|docdown|download|pdfdown/i.test(absolute)) {
      return null;
    }
    if (!absolute.includes("dflag=pdfdown") && /download|docdown/i.test(absolute)) {
      absolute += absolute.includes("?") ? "&dflag=pdfdown" : "?dflag=pdfdown";
    }
    return absolute;
  }

  /**
   * @returns {string | null}
   */
  function findPdfHrefInDom() {
    const direct = document.getElementById("pdfDown");
    if (direct && direct.href) {
      const normalized = normalizePdfHref(direct.href);
      if (normalized) {
        return normalized;
      }
    }
    const selectors = [
      ".btn-dlpdf a",
      'a[href*="docdown.cnki.net"]',
      'a[href*="pdfdown"]',
      'a[href*="dflag=pdf"]',
      'a[title*="PDF"]',
      'a[title*="pdf"]',
      ".reader-toolbar a[href*='download']",
      ".toolbar a[href*='download']",
      "[class*='download'] a[href]",
    ];
    for (const sel of selectors) {
      let nodes = [];
      try {
        nodes = Array.from(document.querySelectorAll(sel));
      } catch {
        nodes = [];
      }
      for (const node of nodes) {
        if (!(node instanceof HTMLAnchorElement) || !node.href) {
          continue;
        }
        const normalized = normalizePdfHref(node.href);
        if (normalized) {
          return normalized;
        }
      }
    }
    return null;
  }

  /**
   * @returns {string[]}
   */
  function guessReaderDownloadUrls() {
    /** @type {string[]} */
    const urls = [];
    try {
      const current = new URL(window.location.href);
      const params = current.searchParams;
      const filename = params.get("filename") || params.get("fileName");
      const tablename = params.get("tablename") || params.get("tableName");
      const invoice = params.get("invoice");
      const query = current.search.slice(1);

      if (query && invoice) {
        urls.push(`${current.origin}/reader/api/download?${query}`);
        urls.push(`${current.origin}/reader/download/pdf?${query}`);
      } else if (query && (filename || tablename)) {
        urls.push(`${current.origin}/reader/api/download?${query}`);
        urls.push(`${current.origin}/reader/download/pdf?${query}`);
      }

      const domParams = extractReaderParamsFromPage();
      const resolvedFilename = filename || domParams.filename;
      const resolvedTable = tablename || domParams.tablename;

      if (resolvedFilename && resolvedTable) {
        let flowDownload =
          `${current.origin}/reader/flowpdf/download?filename=${encodeURIComponent(resolvedFilename)}`
          + `&tablename=${encodeURIComponent(resolvedTable)}`;
        const resolvedInvoice = invoice || domParams.invoice;
        if (resolvedInvoice) {
          flowDownload += `&invoice=${encodeURIComponent(resolvedInvoice)}`;
        }
        urls.push(flowDownload);
        urls.push(
          `${current.origin}/kns/download?filename=${encodeURIComponent(resolvedFilename)}`
            + `&tablename=${encodeURIComponent(resolvedTable)}&dflag=pdfdown`,
        );
      }
    } catch {
      /* ignore malformed location */
    }
    return dedupeUrls(urls);
  }

  /**
   * @returns {{ filename: string, tablename: string, invoice: string }}
   */
  function extractReaderParamsFromPage() {
    /** @type {{ filename: string, tablename: string, invoice: string }} */
    const out = { filename: "", tablename: "", invoice: "" };
    const href = window.location.href;
    const patterns = [
      /[?&]filename=([^&]+)/i,
      /[?&]fileName=([^&]+)/i,
      /"filename"\s*:\s*"([^"]+)"/i,
      /filename\s*[:=]\s*['"]([^'"]+)['"]/i,
    ];
    const tablePatterns = [
      /[?&]tablename=([^&]+)/i,
      /[?&]tableName=([^&]+)/i,
      /"tablename"\s*:\s*"([^"]+)"/i,
      /tablename\s*[:=]\s*['"]([^'"]+)['"]/i,
    ];
    const invoicePatterns = [
      /[?&]invoice=([^&]+)/i,
      /"invoice"\s*:\s*"([^"]+)"/i,
    ];
    for (const pattern of patterns) {
      const match = href.match(pattern);
      if (match && match[1]) {
        out.filename = decodeURIComponent(match[1]);
        break;
      }
    }
    if (!out.filename) {
      const html = document.documentElement ? document.documentElement.innerHTML.slice(0, 250000) : "";
      for (const pattern of patterns.slice(2)) {
        const match = html.match(pattern);
        if (match && match[1]) {
          out.filename = match[1];
          break;
        }
      }
    }
    for (const pattern of tablePatterns) {
      const html = document.documentElement ? document.documentElement.innerHTML.slice(0, 250000) : "";
      const match = href.match(pattern) || html.match(pattern);
      if (match && match[1]) {
        out.tablename = decodeURIComponent(match[1]);
        break;
      }
    }
    for (const pattern of invoicePatterns) {
      const match = href.match(pattern);
      if (match && match[1]) {
        out.invoice = decodeURIComponent(match[1]);
        break;
      }
    }
    return out;
  }

  /**
   * @param {string[]} urls
   * @returns {string[]}
   */
  function dedupeUrls(urls) {
    /** @type {string[]} */
    const out = [];
    urls.forEach((url) => {
      if (url && !out.includes(url)) {
        out.push(url);
      }
    });
    return out;
  }

  /**
   * @returns {{ pdfUrl: string | null, title: string, kind: string, error?: string }}
   */
  function resolvePdfDownload() {
    if (hasVisibleCaptcha()) {
      return { pdfUrl: null, title: readDocumentTitle(), kind: "captcha", error: "CNKI_CAPTCHA" };
    }

    const kind = (() => {
      const path = window.location.pathname.toLowerCase();
      if (path.includes("/reader/flowpdf")) {
        return "flowpdf";
      }
      if (path.includes("/xmlread/trialread") || path.includes("/nzkhtml/xmlread/trialread")) {
        return "trial-read";
      }
      if (path.includes("/kcms2/article") || path.includes("/kcms/detail")) {
        return "detail";
      }
      if (path.includes("/reader/")) {
        return "reader";
      }
      return "other";
    })();

    if (kind === "detail" && looksNotLoggedIn()) {
      return { pdfUrl: null, title: readDocumentTitle(), kind, error: "CNKI_LOGIN_REQUIRED" };
    }

    const domUrl = findPdfHrefInDom();
    if (domUrl) {
      return { pdfUrl: domUrl, title: readDocumentTitle(), kind };
    }

    if (kind === "flowpdf" || kind === "trial-read" || kind === "reader") {
      const guesses = guessReaderDownloadUrls();
      if (guesses.length) {
        return { pdfUrl: guesses[0], title: readDocumentTitle(), kind, guessUrls: guesses };
      }
    }

    return { pdfUrl: null, title: readDocumentTitle(), kind, error: "CNKI_PDF_URL_MISS" };
  }

  global.__MGDocExtractCnki.resolvePdfDownload = resolvePdfDownload;
  global.__MGDocExtractCnki.normalizePdfHref = normalizePdfHref;
  global.__MGDocExtractCnki.extractReaderParamsFromPage = extractReaderParamsFromPage;
})(typeof globalThis !== "undefined" ? globalThis : window);
