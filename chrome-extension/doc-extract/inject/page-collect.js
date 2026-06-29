/**
 * Page-context collectors — canvas, html2canvas, dom-article.
 * Requires html2canvas.min.js injected before html2canvas collect.
 */
(function (global) {
  "use strict";

  /**
   * @param {string[]} hideSelectors
   * @returns {{ images: string[], title: string, pageCount: number }}
   */
  function collectCanvasImages(hideSelectors) {
    if (hideSelectors && hideSelectors.length && global.__MGDocExtractPrep) {
      global.__MGDocExtractPrep.hideElements(hideSelectors);
    }
    const images = [];
    let firstWidth = 800;
    let firstHeight = 1100;
    document.querySelectorAll("canvas").forEach((canvas, idx) => {
      try {
        if (idx === 0) {
          firstWidth = canvas.width || firstWidth;
          firstHeight = canvas.height || firstHeight;
        }
        const data = canvas.toDataURL("image/jpeg", 0.92);
        if (data && data.length > 100) {
          images.push(data);
        }
      } catch {
        /* tainted canvas */
      }
    });
    return {
      images,
      title: document.title || "document",
      pageCount: images.length,
      pageWidth: firstWidth,
      pageHeight: firstHeight,
    };
  }

  /**
   * @param {object} config
   * @returns {Promise<{ images: string[], title: string, pageCount: number }>}
   */
  async function collectHtml2CanvasImages(config) {
    const html2canvasFn = global.html2canvas;
    if (typeof html2canvasFn !== "function") {
      throw new Error("html2canvas not loaded");
    }
    const selectors = (config && config.pageSelectors) || [".page", "article", "main"];
    const images = [];
    let pageWidth = 800;
    let pageHeight = 1100;
    let nodes = [];
    selectors.forEach((sel) => {
      try {
        document.querySelectorAll(sel).forEach((n) => nodes.push(n));
      } catch {
        /* ignore */
      }
    });
    if (!nodes.length) {
      nodes = [document.body];
    }
    for (const node of nodes) {
      if (!(node instanceof HTMLElement)) {
        continue;
      }
      const canvas = await html2canvasFn(node, {
        useCORS: true,
        allowTaint: true,
        scale: 1,
        logging: false,
      });
      if (images.length === 0) {
        pageWidth = canvas.width || pageWidth;
        pageHeight = canvas.height || pageHeight;
      }
      images.push(canvas.toDataURL("image/jpeg", 0.92));
    }
    return {
      images,
      title: document.title || "document",
      pageCount: images.length,
      pageWidth,
      pageHeight,
    };
  }

  /**
   * @param {object} config
   * @returns {{ html: string, text: string, title: string }}
   */
  function collectDomArticle(config) {
    const selectors = (config && config.pageSelectors) || [
      "#articlecontent",
      '[itemprop="articleBody"]',
      '[role="article"]',
      "article",
      "main",
    ];
    let root = null;
    for (const sel of selectors) {
      try {
        root = document.querySelector(sel);
      } catch {
        root = null;
      }
      if (root) {
        break;
      }
    }
    if (!root) {
      root = document.body;
    }
    const html = root ? root.innerHTML || "" : "";
    const text = root ? root.innerText || "" : "";
    return {
      html,
      text,
      title: document.title || "article",
    };
  }

  global.__MGDocExtractCollect = {
    collectCanvasImages,
    collectHtml2CanvasImages,
    collectDomArticle,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
