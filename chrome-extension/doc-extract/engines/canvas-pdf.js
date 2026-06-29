/**
 * jsPDF assembly — port 437609 downloadPDF + 435884 imgs_to_pdf orientation logic.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {string} dataUrl
   * @returns {{ width: number, height: number, format: string }}
   */
  function measureDataUrlImage(dataUrl) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        resolve({
          width: img.naturalWidth || img.width || 800,
          height: img.naturalHeight || img.height || 1100,
          format: "JPEG",
        });
      };
      img.onerror = () => reject(new Error("IMAGE_MEASURE_FAILED"));
      img.src = dataUrl;
    });
  }

  /**
   * @param {string[]} images Data URLs (jpeg/png)
   * @param {string} title
   * @param {{ pageWidth?: number, pageHeight?: number }} [sizeOpts]
   * @returns {Promise<Blob>}
   */
  async function imagesToPdfBlob(images, title, sizeOpts) {
    if (!images || !images.length) {
      throw new Error("NO_IMAGES");
    }
    const jspdfRoot = global.jspdf || global.jsPDF;
    const JsPdfCtor = jspdfRoot && (jspdfRoot.jsPDF || jspdfRoot);
    if (typeof JsPdfCtor !== "function") {
      throw new Error("JSPDF_NOT_LOADED");
    }
    let width = sizeOpts && sizeOpts.pageWidth ? sizeOpts.pageWidth : 800;
    let height = sizeOpts && sizeOpts.pageHeight ? sizeOpts.pageHeight : 1100;
    if (typeof Image !== "undefined") {
      try {
        const first = await measureDataUrlImage(images[0]);
        width = first.width;
        height = first.height;
      } catch {
        /* use page-provided or default size */
      }
    }
    const orientation = width > height ? "landscape" : "portrait";
    const doc = new JsPdfCtor({
      orientation,
      unit: "px",
      format: [width, height],
    });
    doc.setProperties({ title: title || "document" });
    images.forEach((dataUrl, idx) => {
      if (idx > 0) {
        doc.addPage([width, height], orientation);
      }
      doc.addImage(dataUrl, "JPEG", 0, 0, width, height);
    });
    return doc.output("blob");
  }

  /**
   * @param {string[]} images
   * @returns {Promise<Blob>}
   */
  async function imagesToZipBlob(images) {
    const zipRoot = global.JSZip;
    if (typeof zipRoot !== "function") {
      throw new Error("JSZIP_NOT_LOADED");
    }
    const zip = new zipRoot();
    images.forEach((dataUrl, idx) => {
      const base64 = dataUrl.split(",")[1] || "";
      zip.file(`page-${String(idx + 1).padStart(3, "0")}.jpg`, base64, { base64: true });
    });
    return zip.generateAsync({ type: "blob" });
  }

  MindGraphDocExtract.imagesToPdfBlob = imagesToPdfBlob;
  MindGraphDocExtract.imagesToZipBlob = imagesToZipBlob;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);

/**
 * canvas-pdf tab runner — collect canvases in page, assemble in SW.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<{ images: string[], title: string, pageCount: number }>}
   */
  async function collectCanvasFromTab(tabId, hostEntry) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/inject/page-collect.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (hideSelectors) => {
        if (!globalThis.__MGDocExtractCollect) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectCanvasImages(hideSelectors);
      },
      args: [hostEntry.hideSelectors || []],
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
  async function runCanvasPdfEngine(tabId, hostEntry, postProgress) {
    postProgress("collecting");
    const payload = await collectCanvasFromTab(tabId, hostEntry);
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

  MindGraphDocExtract.collectCanvasFromTab = collectCanvasFromTab;
  MindGraphDocExtract.runCanvasPdfEngine = runCanvasPdfEngine;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
