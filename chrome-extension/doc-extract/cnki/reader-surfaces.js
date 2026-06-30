/**
 * Shared CNKI reader surface helpers (canvas, img, iframes).
 */
(function (global) {
  "use strict";

  global.__MGDocExtractCollect = global.__MGDocExtractCollect || {};

  /**
   * @param {number} ms
   * @returns {Promise<void>}
   */
  function sleep(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  /**
   * @returns {Document[]}
   */
  function readerDocuments() {
    /** @type {Document[]} */
    const docs = [document];
    document.querySelectorAll("iframe").forEach((frame) => {
      try {
        if (frame.contentDocument) {
          docs.push(frame.contentDocument);
        }
      } catch {
        /* cross-origin iframe */
      }
    });
    return docs;
  }

  /**
   * @param {number} [maxMs]
   * @returns {Promise<boolean>}
   */
  async function waitForCnkiReaderSurfaces(maxMs) {
    const budget = typeof maxMs === "number" && maxMs > 0 ? maxMs : 4000;
    const start = Date.now();
    while (Date.now() - start < budget) {
      for (const doc of readerDocuments()) {
        if (doc.querySelector("canvas")) {
          return true;
        }
        const img = doc.querySelector(
          "#viewer img, .reader-page img, .page-img, img[class*='page'], img[class*='reader']",
        );
        if (img && img instanceof HTMLImageElement && img.naturalWidth > 120) {
          return true;
        }
      }
      await sleep(250);
    }
    return false;
  }

  /**
   * @param {Set<string>} seen
   * @param {string[]} images
   * @param {number} pageWidth
   * @param {number} pageHeight
   * @returns {{ pageWidth: number, pageHeight: number }}
   */
  function captureVisibleReaderSurfaces(seen, images, pageWidth, pageHeight) {
    let width = pageWidth;
    let height = pageHeight;

    for (const doc of readerDocuments()) {
      doc.querySelectorAll("canvas").forEach((canvas, idx) => {
        if (!(canvas instanceof HTMLCanvasElement)) {
          return;
        }
        try {
          if (idx === 0 && canvas.width && canvas.height) {
            width = canvas.width;
            height = canvas.height;
          }
          const data = canvas.toDataURL("image/jpeg", 0.92);
          if (data && data.length > 100 && !seen.has(data)) {
            seen.add(data);
            images.push(data);
          }
        } catch {
          /* tainted canvas */
        }
      });

      doc.querySelectorAll(
        "#viewer img, .reader-page img, .page-img, img[class*='page'], img[class*='reader'], .page-container img",
      ).forEach((node) => {
        if (!(node instanceof HTMLImageElement)) {
          return;
        }
        if (node.naturalWidth < 120 || node.naturalHeight < 120) {
          return;
        }
        const src = (node.currentSrc || node.src || "").trim();
        if (!src || src.startsWith("data:image/gif")) {
          return;
        }
        try {
          const temp = document.createElement("canvas");
          temp.width = node.naturalWidth;
          temp.height = node.naturalHeight;
          const ctx = temp.getContext("2d");
          if (!ctx) {
            return;
          }
          ctx.drawImage(node, 0, 0);
          const data = temp.toDataURL("image/jpeg", 0.92);
          if (data && data.length > 100 && !seen.has(data)) {
            seen.add(data);
            images.push(data);
            width = node.naturalWidth;
            height = node.naturalHeight;
          }
        } catch {
          if (src.startsWith("data:image/") && src.length > 100 && !seen.has(src)) {
            seen.add(src);
            images.push(src);
          }
        }
      });
    }

    return { pageWidth: width, pageHeight: height };
  }

  /**
   * @param {string[]} selectors
   * @returns {HTMLElement | null}
   */
  function findNextPageControl(selectors) {
    for (const doc of readerDocuments()) {
      for (const sel of selectors) {
        let nodes = [];
        try {
          nodes = Array.from(doc.querySelectorAll(sel));
        } catch {
          nodes = [];
        }
        for (const node of nodes) {
          if (!(node instanceof HTMLElement)) {
            continue;
          }
          if (node.matches(":disabled") || node.getAttribute("aria-disabled") === "true") {
            continue;
          }
          const hidden = node.offsetParent === null && node.tagName !== "BODY";
          if (hidden) {
            continue;
          }
          return node;
        }
      }
    }
    return null;
  }

  global.__MGDocExtractCollect.sleep = sleep;
  global.__MGDocExtractCollect.waitForCnkiReaderSurfaces = waitForCnkiReaderSurfaces;
  global.__MGDocExtractCollect.captureVisibleReaderSurfaces = captureVisibleReaderSurfaces;
  global.__MGDocExtractCollect.findCnkiNextPageControl = findNextPageControl;
  global.__MGDocExtractCollect.readerDocuments = readerDocuments;
})(typeof globalThis !== "undefined" ? globalThis : window);
