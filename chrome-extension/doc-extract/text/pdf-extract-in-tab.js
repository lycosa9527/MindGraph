/**
 * In-tab PDF text extraction.
 * pdf.worker.min.js must be injected before pdf.min.js so parsing stays inside
 * the extension package (no worker URL, no eval).
 */
(function (global) {
  "use strict";

  /**
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractEmbeddedPdfViewerText(maxPages, maxChars) {
    const app = global.PDFViewerApplication;
    if (!app || !app.pdfDocument) {
      return "";
    }
    const pdf = app.pdfDocument;
    const limit = Math.min(pdf.numPages || 0, maxPages > 0 ? maxPages : 120);
    if (!limit) {
      return "";
    }
    const parts = [];
    for (let pageNum = 1; pageNum <= limit; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => (item && item.str ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (pageText) {
        parts.push(pageText);
      }
    }
    let text = parts.join("\n\n").trim();
    if (maxChars > 0 && text.length > maxChars) {
      text = `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
    }
    return text;
  }

  /**
   * @param {ArrayBuffer} pdfBuffer
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractTextFromPdfBuffer(pdfBuffer, maxPages, maxChars) {
    const pdfjsLib = global.pdfjsLib;
    if (!pdfjsLib || typeof pdfjsLib.getDocument !== "function") {
      throw new Error("PDFJS_NOT_LOADED");
    }
    // The packaged worker is already on this realm. pdf.js 3.11 ignores disableWorker
    // and would otherwise construct a Worker from a URL.
    const data = pdfBuffer instanceof ArrayBuffer ? new Uint8Array(pdfBuffer) : pdfBuffer;
    const loadingTask = pdfjsLib.getDocument({ data, isEvalSupported: false });
    const pdf = await loadingTask.promise;
    const limit = Math.min(pdf.numPages || 0, maxPages > 0 ? maxPages : 80);
    const parts = [];
    for (let pageNum = 1; pageNum <= limit; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => (item && item.str ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (pageText) {
        parts.push(pageText);
      }
    }
    let text = parts.join("\n\n").trim();
    if (maxChars > 0 && text.length > maxChars) {
      text = `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
    }
    return text;
  }

  const IMAGE_PAGE_MAX_CHARS = 20;
  const CLASSIFY_SAMPLE_PAGES = 3;

  /**
   * A page is image-based when it paints a picture and has almost no text.
   * @param {number} chars
   * @param {boolean} hasImage
   * @returns {boolean}
   */
  function pageLooksImageBased(chars, hasImage) {
    return Boolean(hasImage) && chars < IMAGE_PAGE_MAX_CHARS;
  }

  /**
   * The file is image-based when every sampled page is an image page.
   * @param {Array<{ imageLike: boolean }>} samples
   * @returns {boolean}
   */
  function documentIsImageBased(samples) {
    if (!Array.isArray(samples) || !samples.length) {
      return false;
    }
    return samples.every((sample) => sample && sample.imageLike);
  }

  /**
   * @param {object} pdfjsLib
   * @returns {number[]}
   */
  function pdfjsImageOperatorIds(pdfjsLib) {
    const ops = pdfjsLib && pdfjsLib.OPS ? pdfjsLib.OPS : {};
    return [
      ops.paintImageXObject,
      ops.paintImageXObjectRepeat,
      ops.paintJpegXObject,
      ops.paintInlineImageXObject,
      ops.paintInlineImageXObjectGroup,
      ops.paintImageMaskXObject,
      ops.paintImageMaskXObjectRepeat,
      ops.paintFormXObject,
    ].filter((op) => typeof op === "number");
  }

  /**
   * @param {ArrayBuffer | Uint8Array} pdfBuffer
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<{ text: string, imageBased: boolean, pageCount: number }>}
   */
  async function classifyPdfBuffer(pdfBuffer, maxPages, maxChars) {
    const pdfjsLib = global.pdfjsLib;
    if (!pdfjsLib || typeof pdfjsLib.getDocument !== "function") {
      throw new Error("PDFJS_NOT_LOADED");
    }
    const data = pdfBuffer instanceof ArrayBuffer ? new Uint8Array(pdfBuffer) : pdfBuffer;
    const loadingTask = pdfjsLib.getDocument({ data, isEvalSupported: false });
    const pdf = await loadingTask.promise;
    const pageCount = pdf.numPages || 0;
    const limit = Math.min(pageCount, maxPages > 0 ? maxPages : 80);
    const sampleLimit = Math.min(limit, CLASSIFY_SAMPLE_PAGES);
    const imageOps = pdfjsImageOperatorIds(pdfjsLib);
    const parts = [];
    /** @type {Array<{ imageLike: boolean }>} */
    const samples = [];
    for (let pageNum = 1; pageNum <= limit; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => (item && item.str ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (pageText) {
        parts.push(pageText);
      }
      if (pageNum <= sampleLimit) {
        const opList = await page.getOperatorList();
        const fnArray = opList && opList.fnArray ? opList.fnArray : [];
        const hasImage = fnArray.some((fnId) => imageOps.indexOf(fnId) !== -1);
        samples.push({ imageLike: pageLooksImageBased(pageText.length, hasImage) });
      }
    }
    let text = parts.join("\n\n").trim();
    if (maxChars > 0 && text.length > maxChars) {
      text = `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
    }
    if (typeof pdf.destroy === "function") {
      await pdf.destroy();
    }
    return {
      text,
      imageBased: documentIsImageBased(samples),
      pageCount,
    };
  }

  global.__MGDocExtractPdf = {
    extractEmbeddedPdfViewerText,
    extractTextFromPdfBuffer,
    pageLooksImageBased,
    documentIsImageBased,
    classifyPdfBuffer,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
