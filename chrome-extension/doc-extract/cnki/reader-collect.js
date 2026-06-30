/**
 * CNKI flowpdf / online reader — flip pages and collect canvas renders.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractCollect = global.__MGDocExtractCollect || {};

  /**
   * @param {string[]} hideSelectors
   * @param {number} [maxPages]
   * @returns {Promise<{ images: string[], title: string, pageCount: number, pageWidth: number, pageHeight: number }>}
   */
  async function collectCnkiReaderCanvasImages(hideSelectors, maxPages) {
    if (hideSelectors && hideSelectors.length && global.__MGDocExtractPrep) {
      global.__MGDocExtractPrep.hideElements(hideSelectors);
    }

    if (typeof global.__MGDocExtractCollect.waitForCnkiReaderSurfaces === "function") {
      await global.__MGDocExtractCollect.waitForCnkiReaderSurfaces(4500);
    }

    const limit = typeof maxPages === "number" && maxPages > 0 ? maxPages : 120;
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

    const seen = new Set();
    /** @type {string[]} */
    const images = [];
    let pageWidth = 800;
    let pageHeight = 1100;

    const capture =
      typeof global.__MGDocExtractCollect.captureVisibleReaderSurfaces === "function"
        ? global.__MGDocExtractCollect.captureVisibleReaderSurfaces
        : null;

    let size = capture
      ? capture(seen, images, pageWidth, pageHeight)
      : { pageWidth, pageHeight };
    pageWidth = size.pageWidth;
    pageHeight = size.pageHeight;

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

    for (let step = 0; step < limit; step += 1) {
      const next = findNext(nextSelectors);
      if (!next) {
        break;
      }
      const before = images.length;
      next.click();
      await sleep(750);
      if (capture) {
        size = capture(seen, images, pageWidth, pageHeight);
        pageWidth = size.pageWidth;
        pageHeight = size.pageHeight;
      }
      if (images.length === before) {
        break;
      }
    }

    let title = document.title || "cnki-document";
    if (global.__MGDocExtractCnki && global.__MGDocExtractCnki.resolvePdfDownload) {
      const resolved = global.__MGDocExtractCnki.resolvePdfDownload();
      if (resolved && resolved.title) {
        title = resolved.title;
      }
    }

    return {
      images,
      title,
      pageCount: images.length,
      pageWidth,
      pageHeight,
    };
  }

  global.__MGDocExtractCollect.collectCnkiReaderCanvasImages = collectCnkiReaderCanvasImages;
})(typeof globalThis !== "undefined" ? globalThis : window);
