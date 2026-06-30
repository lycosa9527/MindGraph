/**
 * Fetch PDF bytes from browser PDF tab URLs (native Chrome/Edge viewer tabs).
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphShared = global.MindGraphShared;

  /**
   * @param {string} pageUrl
   * @returns {Promise<Blob | null>}
   */
  async function fetchPdfBlobFromBrowserTabUrl(pageUrl) {
    if (!MindGraphShared || typeof MindGraphShared.isBrowserPdfTabUrl !== "function") {
      return null;
    }
    if (!MindGraphShared.isBrowserPdfTabUrl(pageUrl)) {
      return null;
    }
    try {
      const res = await fetch(pageUrl, {
        method: "GET",
        credentials: "include",
        redirect: "follow",
        headers: {
          Accept: "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        },
      });
      if (!res.ok) {
        return null;
      }
      const blob = await res.blob();
      const buffer = await blob.arrayBuffer();
      if (MindGraphDocExtract.isPdfBytes && MindGraphDocExtract.isPdfBytes(buffer)) {
        return blob;
      }
      const type = (blob.type || "").toLowerCase();
      if (type.includes("pdf") || type.includes("octet-stream")) {
        return blob;
      }
      return null;
    } catch {
      return null;
    }
  }

  /**
   * @param {string} pageUrl
   * @returns {string}
   */
  function titleFromBrowserPdfUrl(pageUrl) {
    try {
      const parsed = new URL(pageUrl);
      const base = decodeURIComponent(parsed.pathname.split("/").pop() || "document.pdf");
      return base.replace(/\.pdf$/i, "") || "PDF document";
    } catch {
      return "PDF document";
    }
  }

  MindGraphDocExtract.fetchPdfBlobFromBrowserTabUrl = fetchPdfBlobFromBrowserTabUrl;
  MindGraphDocExtract.titleFromBrowserPdfUrl = titleFromBrowserPdfUrl;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
