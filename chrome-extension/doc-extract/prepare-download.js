/**
 * Blob download URL preparation — shared by PNG and document extract.
 * Mirrors background.js prepareDownloadUrlFromPngBlob (generic mime).
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  let offscreenBlobReady = false;
  /** @type {Promise<void> | null} */
  let offscreenBlobBootstrapping = null;
  const OFFSCREEN_BLOB_PAGE = "offscreen.html";

  /**
   * @returns {object | null}
   */
  function getOffscreenApi() {
    if (typeof chrome !== "undefined" && chrome.offscreen) {
      return chrome.offscreen;
    }
    if (global.browser && global.browser.offscreen) {
      return global.browser.offscreen;
    }
    return null;
  }

  /**
   * @returns {boolean}
   */
  function serviceWorkerHasBlobObjectUrl() {
    const U = global.URL;
    return Boolean(
      U && typeof U.createObjectURL === "function" && typeof U.revokeObjectURL === "function",
    );
  }

  /**
   * @param {object} offApi
   * @returns {Promise<void>}
   */
  async function ensureOffscreenDocumentForBlobs(offApi) {
    if (offscreenBlobReady) {
      return;
    }
    if (offscreenBlobBootstrapping) {
      return offscreenBlobBootstrapping;
    }
    const offscreenUrl = chrome.runtime.getURL(OFFSCREEN_BLOB_PAGE);
    offscreenBlobBootstrapping = (async () => {
      if (chrome.runtime.getContexts) {
        const existing = await chrome.runtime.getContexts({
          contextTypes: ["OFFSCREEN_DOCUMENT"],
          documentUrls: [offscreenUrl],
        });
        if (existing && existing.length > 0) {
          offscreenBlobReady = true;
          return;
        }
      }
      try {
        await offApi.createDocument({
          url: OFFSCREEN_BLOB_PAGE,
          reasons: ["BLOBS"],
          justification: "MindGraph document extract download blobs.",
        });
      } catch (e) {
        const text = (e && e.message) || String(e);
        if (!/only a single|already exists|offscreen|OFFSCREEN|single offscreen/i.test(text)) {
          throw e;
        }
      }
      offscreenBlobReady = true;
    })();
    try {
      await offscreenBlobBootstrapping;
    } finally {
      offscreenBlobBootstrapping = null;
    }
  }

  /**
   * @param {Blob} blob
   * @returns {Promise<string>}
   */
  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result));
      fr.onerror = () => reject(fr.error || new Error("FileReader"));
      fr.readAsDataURL(blob);
    });
  }

  /**
   * @param {Blob} blob
   * @returns {Promise<string>}
   */
  async function createBlobObjectUrlInOffscreen(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    const chunkSize = 8192;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    const base64 = btoa(binary);
    const mimeType = blob.type || "application/octet-stream";
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "MINDGRAPH_BLOB_URL", base64, mimeType }, (response) => {
        const last = chrome.runtime.lastError;
        if (last) {
          reject(new Error(last.message));
          return;
        }
        if (response && response.ok && typeof response.href === "string") {
          resolve(response.href);
          return;
        }
        reject(new Error((response && response.error) || "BLOB_URL_FAILED"));
      });
    });
  }

  /**
   * @param {Blob} blob
   * @returns {Promise<{ href: string, revokeMode: "sw" | "offscreen" | "none" }>}
   */
  async function prepareDownloadUrlFromBlob(blob) {
    if (serviceWorkerHasBlobObjectUrl()) {
      try {
        return { href: global.URL.createObjectURL(blob), revokeMode: "sw" };
      } catch {
        /* fall through */
      }
    }
    const offApi = getOffscreenApi();
    if (offApi) {
      await ensureOffscreenDocumentForBlobs(offApi);
      const href = await createBlobObjectUrlInOffscreen(blob);
      return { href, revokeMode: "offscreen" };
    }
    return { href: await blobToDataUrl(blob), revokeMode: "none" };
  }

  /**
   * @param {string} href
   * @param {"sw" | "offscreen" | "none"} revokeMode
   */
  function scheduleDownloadUrlRevoke(href, revokeMode) {
    if (revokeMode === "none") {
      return;
    }
    if (revokeMode === "sw") {
      setTimeout(() => {
        try {
          if (global.URL && global.URL.revokeObjectURL) {
            global.URL.revokeObjectURL(href);
          }
        } catch {
          /* ignore */
        }
      }, 60_000);
      return;
    }
    setTimeout(() => {
      chrome.runtime.sendMessage({ type: "MINDGRAPH_REVOKE_BLOB_URL", href }, () => {
        void chrome.runtime.lastError;
      });
    }, 60_000);
  }

  MindGraphDocExtract.prepareDownloadUrlFromBlob = prepareDownloadUrlFromBlob;
  MindGraphDocExtract.scheduleDownloadUrlRevoke = scheduleDownloadUrlRevoke;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
