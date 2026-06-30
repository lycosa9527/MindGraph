/**
 * CNKI URL parsing — flowpdf reader, trial read, kcms detail pages.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {string} pageUrl
   * @returns {boolean}
   */
  function isCnkiHostUrl(pageUrl) {
    if (!pageUrl || typeof pageUrl !== "string") {
      return false;
    }
    try {
      return new URL(pageUrl).hostname.toLowerCase().includes("cnki.net");
    } catch {
      return false;
    }
  }

  /**
   * @param {string} pageUrl
   * @returns {"flowpdf"|"trial-read"|"detail"|"reader"|"other"}
   */
  function classifyCnkiPageKind(pageUrl) {
    try {
      const parsed = new URL(pageUrl);
      const path = parsed.pathname.toLowerCase();
      if (path.includes("/reader/flowpdf")) {
        return "flowpdf";
      }
      if (path.includes("/xmlread/trialread") || path.includes("/nzkhtml/xmlread/trialread")) {
        return "trial-read";
      }
      if (path.includes("/kcms2/article") || path.includes("/kcms/detail") || path.includes("/article/abstract")) {
        return "detail";
      }
      if (path.includes("/reader/")) {
        return "reader";
      }
      return "other";
    } catch {
      return "other";
    }
  }

  /**
   * @param {string} pageUrl
   * @returns {object | null}
   */
  function parseCnkiPageUrl(pageUrl) {
    if (!isCnkiHostUrl(pageUrl)) {
      return null;
    }
    try {
      const parsed = new URL(pageUrl);
      const params = parsed.searchParams;
      const kind = classifyCnkiPageKind(pageUrl);
      return {
        kind,
        origin: parsed.origin,
        filename: params.get("filename") || params.get("fileName") || "",
        tablename: params.get("tablename") || params.get("tableName") || "",
        dbcode: params.get("dbcode") || params.get("dbCode") || "",
        product: params.get("product") || "",
        platform: params.get("platform") || "NZKPT",
        invoice: params.get("invoice") || "",
        dflag: params.get("dflag") || "",
      };
    } catch {
      return null;
    }
  }

  /**
   * @param {string} pageUrl
   * @returns {string[]}
   */
  function buildCnkiReaderDownloadCandidates(pageUrl) {
    const parsed = parseCnkiPageUrl(pageUrl);
    if (!parsed) {
      return [];
    }
    /** @type {string[]} */
    const urls = [];
    try {
      const current = new URL(pageUrl);
      const query = current.search.slice(1);
      if (query && parsed.invoice) {
        urls.push(`${current.origin}/reader/api/download?${query}`);
        urls.push(`${current.origin}/reader/download/pdf?${query}`);
      } else if (query && (parsed.filename || parsed.tablename)) {
        urls.push(`${current.origin}/reader/api/download?${query}`);
        urls.push(`${current.origin}/reader/download/pdf?${query}`);
      }
      if (parsed.filename && parsed.tablename) {
        let flowDownload =
          `${current.origin}/reader/flowpdf/download?filename=${encodeURIComponent(parsed.filename)}`
          + `&tablename=${encodeURIComponent(parsed.tablename)}`;
        if (parsed.invoice) {
          flowDownload += `&invoice=${encodeURIComponent(parsed.invoice)}`;
        }
        urls.push(flowDownload);
        urls.push(
          `${current.origin}/kns/download?filename=${encodeURIComponent(parsed.filename)}`
            + `&tablename=${encodeURIComponent(parsed.tablename)}&dflag=pdfdown`,
        );
      }
    } catch {
      return [];
    }
    /** @type {string[]} */
    const deduped = [];
    urls.forEach((url) => {
      if (url && !deduped.includes(url)) {
        deduped.push(url);
      }
    });
    return deduped;
  }

  MindGraphDocExtract.isCnkiHostUrl = isCnkiHostUrl;
  MindGraphDocExtract.classifyCnkiPageKind = classifyCnkiPageKind;
  MindGraphDocExtract.parseCnkiPageUrl = parseCnkiPageUrl;
  MindGraphDocExtract.buildCnkiReaderDownloadCandidates = buildCnkiReaderDownloadCandidates;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
