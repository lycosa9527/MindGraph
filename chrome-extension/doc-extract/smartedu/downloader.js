/**
 * SmartEdu binary download — mirrors file_reader/smartedu/downloader.py.
 * Keep auth headers and URL suffix rules in sync with the file-reader SmartEdu tab.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const appendAccessTokenQuery = MindGraphDocExtract.appendAccessTokenQuery;

  /**
   * @param {string} title
   * @param {string} ext
   * @returns {string}
   */
  function sanitizeDownloadBasename(title, ext) {
    const base = (title || "smartedu")
      .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
      .slice(0, 80);
    const suffix = ext.startsWith(".") ? ext : `.${ext}`;
    return base.toLowerCase().endsWith(suffix.toLowerCase()) ? base : `${base}${suffix}`;
  }

  /**
   * @param {object} asset
   * @returns {string}
   */
  function guessAssetExtension(asset) {
    if (asset.localKind === "m3u8") {
      return ".m3u8.txt";
    }
    if (asset.localKind === "pdf" || asset.format === "pdf") {
      return ".pdf";
    }
    const url = asset.downloadUrl || "";
    const m = url.match(/\.([a-z0-9]{2,5})(?:\?|$)/i);
    if (m) {
      return `.${m[1].toLowerCase()}`;
    }
    return ".bin";
  }

  /**
   * @param {object} asset
   * @param {string | null | undefined} accessToken
   * @param {Record<string, string>} authHeaders
   * @returns {Promise<{ blob: Blob, filename: string, m3u8Url?: string }>}
   */
  async function downloadSmartEduAsset(asset, accessToken, authHeaders) {
    let url = appendAccessTokenQuery(asset.downloadUrl, accessToken);
    if (asset.localKind === "m3u8") {
      return {
        blob: new Blob([url], { type: "text/plain;charset=utf-8" }),
        filename: sanitizeDownloadBasename(asset.title, ".m3u8.txt"),
        m3u8Url: url,
      };
    }
    const res = await fetch(url, {
      method: "GET",
      headers: {
        ...authHeaders,
      },
    });
    if (!res.ok) {
      throw new Error(`SmartEdu download HTTP ${res.status} (${asset.title})`);
    }
    const blob = await res.blob();
    const ext = guessAssetExtension(asset);
    return {
      blob,
      filename: sanitizeDownloadBasename(asset.title, ext),
    };
  }

  /**
   * @param {Array<object>} assets
   * @param {string | null | undefined} accessToken
   * @param {(done: number, total: number, label: string) => void} [onProgress]
   * @returns {Promise<Array<{ blob: Blob, filename: string, m3u8Url?: string }>>}
   */
  async function downloadSmartEduAssets(assets, accessToken, onProgress) {
    const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(accessToken);
    const selected = assets.filter((a) => a.selected !== false);
    const out = [];
    for (let i = 0; i < selected.length; i += 1) {
      const asset = selected[i];
      if (onProgress) {
        onProgress(i, selected.length, asset.title);
      }
      out.push(await downloadSmartEduAsset(asset, accessToken, authHeaders));
    }
    if (onProgress) {
      onProgress(selected.length, selected.length, "done");
    }
    return out;
  }

  MindGraphDocExtract.sanitizeDownloadBasename = sanitizeDownloadBasename;
  MindGraphDocExtract.downloadSmartEduAsset = downloadSmartEduAsset;
  MindGraphDocExtract.downloadSmartEduAssets = downloadSmartEduAssets;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
