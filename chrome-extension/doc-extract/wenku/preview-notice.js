/**
 * Baidu Wenku free-preview detection — 8-page cap + VIP paywall hints.
 */
(function (global) {
  "use strict";

  const WENKU_PREVIEW_PAGE_CAP = 8;

  /**
   * @param {number} pageCount
   * @param {string} hostname
   * @param {string} bodyText
   * @returns {{ key: string, pageCount: string } | null}
   */
  function evaluateWenkuPreviewNotice(pageCount, hostname, bodyText) {
    const host = (hostname || "").toLowerCase();
    if (!host.includes("wenku.baidu.com")) {
      return null;
    }
    if (typeof pageCount !== "number" || pageCount < 1) {
      return null;
    }
    const text = bodyText || "";
    const paywallHints =
      /VIP|开通文库|成为VIP|文库VIP|剩余\s*\d+\s*页|付费阅读|下载券|续费会员|开通会员/i.test(text);
    if (pageCount <= WENKU_PREVIEW_PAGE_CAP && (paywallHints || pageCount === WENKU_PREVIEW_PAGE_CAP)) {
      return {
        key: "statusWenkuPreviewLimited",
        pageCount: String(pageCount),
      };
    }
    return null;
  }

  global.__MGWenkuPreview = {
    evaluateWenkuPreviewNotice,
    WENKU_PREVIEW_PAGE_CAP,
  };

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.evaluateWenkuPreviewNotice = evaluateWenkuPreviewNotice;
  MindGraphDocExtract.WENKU_PREVIEW_PAGE_CAP = WENKU_PREVIEW_PAGE_CAP;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
