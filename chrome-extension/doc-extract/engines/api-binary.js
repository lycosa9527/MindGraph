/**
 * api-binary engine — SmartEdu via doc-extract/smartedu/; wenku reader URL tier.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * Wenku API tier (wks / BaiduWenkuSpider pattern) — best-effort direct PDF URL.
   * @param {string} pageUrl
   * @returns {string | null}
   */
  function guessWenkuReaderPdfUrl(pageUrl) {
    try {
      const parsed = new URL(pageUrl);
      if (!parsed.hostname.includes("wenku.baidu.com")) {
        return null;
      }
      const pathMatch = parsed.pathname.match(/\/view\/([a-f0-9]+)/i);
      if (!pathMatch) {
        return null;
      }
      return `https://wkretype.bdimg.com/retype/api/getdoc?type=pdf&rn=1&pn=0&md5sum=${pathMatch[1]}&wkQuery=1`;
    } catch {
      return null;
    }
  }

  /**
   * @param {string} url
   * @returns {Promise<Blob>}
   */
  async function fetchBinaryUrl(url) {
    const res = await fetch(url, { method: "GET" });
    if (!res.ok) {
      throw new Error(`BINARY_HTTP_${res.status}`);
    }
    return res.blob();
  }

  /**
   * @param {number} tabId
   * @param {string | null | undefined} pastedToken
   * @returns {Promise<string | null>}
   */
  async function resolveSmartEduToken(tabId, pastedToken) {
    const trimmed = (pastedToken || "").trim();
    if (trimmed) {
      return trimmed;
    }
    const stored = await chrome.storage.local.get(["smarteduAccessToken"]);
    if (stored.smarteduAccessToken) {
      return String(stored.smarteduAccessToken);
    }
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: MindGraphDocExtract.readSmartEduTokenFromPage,
      });
      const token = results && results[0] && results[0].result && results[0].result.accessToken;
      if (token) {
        await chrome.storage.local.set({ smarteduAccessToken: token });
        return token;
      }
    } catch {
      /* ignore */
    }
    return null;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {(stage: string) => void} postProgress
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ blob: Blob, filename: string, multi?: Array<{ blob: Blob, filename: string }> }>}
   */
  async function runApiBinaryEngine(tabId, hostEntry, pageUrl, postProgress, options) {
    if (hostEntry.id === "smartedu") {
      const parsed = MindGraphDocExtract.parseSmartEduUrl(pageUrl);
      if (!parsed) {
        throw new Error("SMARTEDU_URL_INVALID");
      }
      postProgress("collecting");
      const token = await resolveSmartEduToken(tabId, options && options.smarteduToken);
      const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(token);
      const meta = await MindGraphDocExtract.fetchSmartEduMetadata(parsed.detailUrl, authHeaders);
      let assets = meta.assets;
      if (options && options.smarteduAssets && options.smarteduAssets.length) {
        assets = options.smarteduAssets;
      }
      if (!assets.length) {
        throw new Error("SMARTEDU_NO_ASSETS");
      }
      postProgress("assembling");
      const downloads = await MindGraphDocExtract.downloadSmartEduAssets(
        assets,
        token,
        () => {},
      );
      if (downloads.length === 1) {
        return downloads[0];
      }
      return {
        blob: downloads[0].blob,
        filename: downloads[0].filename,
        multi: downloads,
      };
    }

    if (hostEntry.id === "wenku") {
      const directUrl = guessWenkuReaderPdfUrl(pageUrl);
      if (directUrl) {
        postProgress("collecting");
        const blob = await fetchBinaryUrl(directUrl);
        postProgress("assembling");
        return {
          blob,
          filename: MindGraphDocExtract.sanitizeDownloadBasename(documentTitleFromUrl(pageUrl), ".pdf"),
        };
      }
      throw new Error("WENKU_API_TIER_MISS");
    }

    throw new Error("API_BINARY_UNSUPPORTED_HOST");
  }

  /**
   * @param {string} pageUrl
   * @returns {string}
   */
  function documentTitleFromUrl(pageUrl) {
    try {
      return decodeURIComponent(new URL(pageUrl).pathname.split("/").pop() || "document");
    } catch {
      return "document";
    }
  }

  MindGraphDocExtract.guessWenkuReaderPdfUrl = guessWenkuReaderPdfUrl;
  MindGraphDocExtract.runApiBinaryEngine = runApiBinaryEngine;
  MindGraphDocExtract.resolveSmartEduToken = resolveSmartEduToken;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
