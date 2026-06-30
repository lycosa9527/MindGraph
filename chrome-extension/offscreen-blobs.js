/**
 * Shared blob → download URL preparation for PNG and document extract.
 * Single offscreen bootstrap avoids duplicate createDocument races (Edge + Chrome).
 */
(function (global) {
  "use strict";

  const OFFSCREEN_BLOB_PAGE = "offscreen.html";
  let offscreenBlobReady = false;
  /** @type {Promise<void> | null} */
  let offscreenBlobBootstrapping = null;

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
   * Edge MV3 often exposes createObjectURL in the worker but blob: downloads fail.
   * @returns {boolean}
   */
  function shouldTryServiceWorkerBlobUrl() {
    if (
      typeof MindGraphShared !== "undefined" &&
      MindGraphShared &&
      typeof MindGraphShared.preferOffscreenBlobUrls === "function" &&
      MindGraphShared.preferOffscreenBlobUrls()
    ) {
      return false;
    }
    return serviceWorkerHasBlobObjectUrl();
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
          url: offscreenUrl,
          reasons: ["BLOBS"],
          justification:
            "MindGraph uses an offscreen document (BLOBS) for blob download URLs when the service worker cannot create them.",
        });
      } catch (e) {
        if (!MindGraphShared.isOffscreenDuplicateError(e)) {
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
   * @param {ArrayBuffer} arrayBuffer
   * @returns {string}
   */
  function arrayBufferToBase64(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    const chunkSize = 8192;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  /**
   * @param {object} payload
   * @returns {Promise<string>}
   */
  function sendBlobUrlRequest(payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(payload, (response) => {
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
   * Prefer structured-clone ArrayBuffer (smaller/faster than base64); fall back for older hosts.
   * @param {Blob} blob
   * @returns {Promise<string>}
   */
  async function createBlobObjectUrlInOffscreen(blob) {
    const mimeType = blob.type || "application/octet-stream";
    const arrayBuffer = await blob.arrayBuffer();
    try {
      return await sendBlobUrlRequest({
        type: "MINDGRAPH_BLOB_URL",
        buffer: arrayBuffer,
        mimeType,
      });
    } catch {
      const base64 = arrayBufferToBase64(arrayBuffer);
      return sendBlobUrlRequest({
        type: "MINDGRAPH_BLOB_URL",
        base64,
        mimeType,
      });
    }
  }

  /**
   * @param {Blob} blob
   * @returns {Promise<{ href: string, revokeMode: "sw" | "offscreen" | "none" }>}
   */
  async function prepareDownloadUrlFromBlob(blob) {
    if (shouldTryServiceWorkerBlobUrl()) {
      try {
        return { href: global.URL.createObjectURL(blob), revokeMode: "sw" };
      } catch (e) {
        console.warn("[MindGraph] URL.createObjectURL in service worker failed, using next path", e);
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

  global.MindGraphOffscreenBlobs = {
    arrayBufferToBase64,
    prepareDownloadUrlFromBlob,
    scheduleDownloadUrlRevoke,
    ensureOffscreenDocumentReady: async () => {
      const offApi = getOffscreenApi();
      if (offApi) {
        await ensureOffscreenDocumentForBlobs(offApi);
      }
    },
  };
})(typeof self !== "undefined" ? self : globalThis);
