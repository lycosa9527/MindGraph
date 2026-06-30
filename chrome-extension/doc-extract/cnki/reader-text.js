/**
 * CNKI flowpdf / online reader — flip pages and collect visible text layers.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractCollect = global.__MGDocExtractCollect || {};

  /**
   * @param {string} text
   * @returns {string}
   */
  function normalizeWhitespace(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  /**
   * @returns {Document[]}
   */
  function readerDocuments() {
    if (typeof global.__MGDocExtractCollect.readerDocuments === "function") {
      return global.__MGDocExtractCollect.readerDocuments();
    }
    return [document];
  }

  /**
   * @returns {string}
   */
  function extractVisibleReaderText() {
    /** @type {string[]} */
    const chunks = [];
    const layerSelectors = [
      "#viewer .textLayer span",
      ".textLayer span",
      '[class*="textLayer"] span',
      ".pdf-text-layer span",
      ".reader-text span",
    ];
    for (const doc of readerDocuments()) {
      for (const sel of layerSelectors) {
        doc.querySelectorAll(sel).forEach((node) => {
          const piece = normalizeWhitespace(node.textContent || "");
          if (piece.length >= 2) {
            chunks.push(piece);
          }
        });
        if (chunks.length >= 8) {
          break;
        }
      }
    }

    if (!chunks.length) {
      for (const doc of readerDocuments()) {
        const pageRoot = doc.querySelector(
          "#viewer .page, .reader-page, .pageContainer, .canvas-wrapper, .page-content",
        );
        if (!pageRoot) {
          continue;
        }
        const clone = pageRoot.cloneNode(true);
        clone.querySelectorAll("canvas, script, style, .toolbar, .textLayer, noscript").forEach((node) => {
          node.remove();
        });
        const fallback = normalizeWhitespace(clone.textContent || "");
        if (fallback.length >= 20) {
          chunks.push(fallback);
          break;
        }
      }
    }

    return normalizeWhitespace(chunks.join(" "));
  }

  /**
   * @param {string[]} hideSelectors
   * @param {number} [maxPages]
   * @param {number} [maxChars]
   * @returns {Promise<{ text: string, title: string, pageCount: number }>}
   */
  async function collectCnkiReaderPlainText(hideSelectors, maxPages, maxChars) {
    if (hideSelectors && hideSelectors.length && global.__MGDocExtractPrep) {
      global.__MGDocExtractPrep.hideElements(hideSelectors);
    }

    if (typeof global.__MGDocExtractCollect.waitForCnkiReaderSurfaces === "function") {
      await global.__MGDocExtractCollect.waitForCnkiReaderSurfaces(4500);
    }

    const limit = typeof maxPages === "number" && maxPages > 0 ? maxPages : 120;
    const charBudget = typeof maxChars === "number" && maxChars > 0 ? maxChars : 8000;
    const nextSelectors = [
      "#nextPage",
      "#next",
      ".next-page",
      ".page-next",
      ".reader-next",
      'button[title*="下一页"]',
      'a[title*="下一页"]',
      '[aria-label*="下一页"]',
      '[aria-label*="Next"]',
      ".toolbar .next",
      ".reader-toolbar .next",
      ".btn-next",
      ".turn-next",
    ];

    /** @type {string[]} */
    const pageTexts = [];
    const seen = new Set();

    function appendPageText(text) {
      const normalized = normalizeWhitespace(text);
      if (normalized.length < 12 || seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      pageTexts.push(normalized);
    }

    const findNext =
      typeof global.__MGDocExtractCollect.findCnkiNextPageControl === "function"
        ? global.__MGDocExtractCollect.findCnkiNextPageControl
        : () => null;
    const sleep =
      typeof global.__MGDocExtractCollect.sleep === "function"
        ? global.__MGDocExtractCollect.sleep
        : (ms) => new Promise((resolve) => {
          setTimeout(resolve, ms);
        });

    appendPageText(extractVisibleReaderText());

    for (let step = 0; step < limit; step += 1) {
      const next = findNext(nextSelectors);
      if (!next) {
        break;
      }
      const before = pageTexts.length;
      next.click();
      await sleep(750);
      appendPageText(extractVisibleReaderText());
      if (pageTexts.length === before) {
        break;
      }
    }

    let combined = pageTexts.join("\n\n").trim();
    if (combined.length > charBudget) {
      combined = `${combined.slice(0, Math.max(0, charBudget - 20)).trim()}\n\n…`;
    }

    let title = document.title || "cnki-document";
    if (global.__MGDocExtractCnki && global.__MGDocExtractCnki.resolvePdfDownload) {
      const resolved = global.__MGDocExtractCnki.resolvePdfDownload();
      if (resolved && resolved.title) {
        title = resolved.title;
      }
    }

    return {
      text: combined,
      title,
      pageCount: pageTexts.length,
    };
  }

  global.__MGDocExtractCollect.collectCnkiReaderPlainText = collectCnkiReaderPlainText;
})(typeof globalThis !== "undefined" ? globalThis : window);
