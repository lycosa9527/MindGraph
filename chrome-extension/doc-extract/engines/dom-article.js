/**
 * DOM article export — 360doc #articlecontent + generic article selectors.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<{ html: string, text: string, title: string }>}
   */
  async function collectDomArticleFromTab(tabId, hostEntry) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/inject/page-collect.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (config) => {
        if (!globalThis.__MGDocExtractCollect) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectDomArticle(config);
      },
      args: [
        {
          pageSelectors: hostEntry.pageSelectors || [],
        },
      ],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || (!payload.text && !payload.html)) {
      throw new Error("DOM_ARTICLE_EMPTY");
    }
    return payload;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<{ blob: Blob, filename: string }>}
   */
  async function runDomArticleEngine(tabId, hostEntry, postProgress) {
    postProgress("collecting");
    const payload = await collectDomArticleFromTab(tabId, hostEntry);
    postProgress("assembling");
    const preferHtml = hostEntry.id === "360doc" || hostEntry.id === "collab_docs";
    const body = preferHtml && payload.html ? payload.html : payload.text;
    const mime = preferHtml && payload.html ? "text/html;charset=utf-8" : "text/plain;charset=utf-8";
    const ext = preferHtml && payload.html ? ".html" : ".txt";
    const blob = new Blob([body], { type: mime });
    const filename = MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ext);
    return { blob, filename };
  }

  MindGraphDocExtract.collectDomArticleFromTab = collectDomArticleFromTab;
  MindGraphDocExtract.runDomArticleEngine = runDomArticleEngine;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
