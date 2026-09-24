/**
 * Bundle JPEG data-URLs into a PDF without third-party libraries.
 * Avoids jsPDF UMD plugins that Chrome Web Store flags as remotely hosted code.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {string} dataUrl
   * @returns {{ bytes: Uint8Array, width: number, height: number }}
   */
  function decodeJpegDataUrl(dataUrl) {
    const match = /^data:image\/jpeg;base64,(.+)$/i.exec(dataUrl || "");
    if (!match) {
      throw new Error("JPEG_DATA_URL_REQUIRED");
    }
    const binary = atob(match[1]);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    const size = readJpegDimensions(bytes);
    return { bytes, width: size.width, height: size.height };
  }

  /**
   * @param {Uint8Array} bytes
   * @returns {{ width: number, height: number }}
   */
  function readJpegDimensions(bytes) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 0xff) {
        break;
      }
      const marker = bytes[offset + 1];
      const length = (bytes[offset + 2] << 8) | bytes[offset + 3];
      if (marker === 0xc0 || marker === 0xc1 || marker === 0xc2) {
        const height = (bytes[offset + 5] << 8) | bytes[offset + 6];
        const width = (bytes[offset + 7] << 8) | bytes[offset + 8];
        if (width > 0 && height > 0) {
          return { width, height };
        }
      }
      if (length < 2) {
        break;
      }
      offset += 2 + length;
    }
    return { width: 800, height: 1100 };
  }

  /**
   * @param {string} value
   * @returns {string}
   */
  function escapePdfLiteral(value) {
    return String(value || "")
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)");
  }

  /**
   * @param {string[]} images JPEG data URLs
   * @param {string} title
   * @param {{ pageWidth?: number, pageHeight?: number }} [sizeOpts]
   * @returns {Promise<Blob>}
   */
  async function imagesToPdfBlob(images, title, sizeOpts) {
    if (!images || !images.length) {
      throw new Error("NO_IMAGES");
    }
    const pages = images.map((dataUrl) => decodeJpegDataUrl(dataUrl));
    let pageWidth = sizeOpts && sizeOpts.pageWidth ? sizeOpts.pageWidth : pages[0].width;
    let pageHeight = sizeOpts && sizeOpts.pageHeight ? sizeOpts.pageHeight : pages[0].height;
    if (!(pageWidth > 0) || !(pageHeight > 0)) {
      pageWidth = pages[0].width;
      pageHeight = pages[0].height;
    }

    const encoder = new TextEncoder();
    /** @type {Uint8Array[]} */
    const chunks = [];
    /** @type {number[]} */
    const offsets = [0];
    let length = 0;

    /**
     * @param {string|Uint8Array} part
     */
    function push(part) {
      const bytes = typeof part === "string" ? encoder.encode(part) : part;
      chunks.push(bytes);
      length += bytes.length;
    }

    /**
     * @returns {number}
     */
    function markObject() {
      offsets.push(length);
      return offsets.length - 1;
    }

    push("%PDF-1.4\n");
    push(new Uint8Array([0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]));

    const catalogObj = markObject();
    const pagesObj = catalogObj + 1;
    push(`${catalogObj} 0 obj\n<< /Type /Catalog /Pages ${pagesObj} 0 R >>\nendobj\n`);

    const pageCount = pages.length;
    const firstPageObj = pagesObj + 1;
    const kids = [];
    for (let i = 0; i < pageCount; i += 1) {
      kids.push(`${firstPageObj + i * 3} 0 R`);
    }
    markObject();
    push(
      `${pagesObj} 0 obj\n<< /Type /Pages /Kids [${kids.join(" ")}] /Count ${pageCount} >>\nendobj\n`,
    );

    const infoObj = firstPageObj + pageCount * 3;
    for (let i = 0; i < pageCount; i += 1) {
      const page = pages[i];
      const pageObj = firstPageObj + i * 3;
      const contentObj = pageObj + 1;
      const imageObj = pageObj + 2;
      const w = pageWidth;
      const h = pageHeight;
      const content = `q\n${w} 0 0 ${h} 0 0 cm\n/Im${i} Do\nQ\n`;

      markObject();
      push(
        `${pageObj} 0 obj\n<< /Type /Page /Parent ${pagesObj} 0 R /MediaBox [0 0 ${w} ${h}] ` +
          `/Resources << /XObject << /Im${i} ${imageObj} 0 R >> >> /Contents ${contentObj} 0 R >>\nendobj\n`,
      );

      markObject();
      push(
        `${contentObj} 0 obj\n<< /Length ${content.length} >>\nstream\n${content}endstream\nendobj\n`,
      );

      markObject();
      push(
        `${imageObj} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} ` +
          `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.bytes.length} >>\nstream\n`,
      );
      push(page.bytes);
      push("\nendstream\nendobj\n");
    }

    markObject();
    push(
      `${infoObj} 0 obj\n<< /Title (${escapePdfLiteral(title || "document")}) /Producer (MindGraph) >>\nendobj\n`,
    );

    const xrefStart = length;
    push(`xref\n0 ${offsets.length}\n`);
    push("0000000000 65535 f \n");
    for (let i = 1; i < offsets.length; i += 1) {
      push(`${String(offsets[i]).padStart(10, "0")} 00000 n \n`);
    }
    push(
      `trailer\n<< /Size ${offsets.length} /Root ${catalogObj} 0 R /Info ${infoObj} 0 R >>\n` +
        `startxref\n${xrefStart}\n%%EOF\n`,
    );

    const out = new Uint8Array(length);
    let cursor = 0;
    chunks.forEach((chunk) => {
      out.set(chunk, cursor);
      cursor += chunk.length;
    });
    return new Blob([out], { type: "application/pdf" });
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
