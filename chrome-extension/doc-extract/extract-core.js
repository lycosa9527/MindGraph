/**
 * Document extract orchestration — prep → collect → assemble → download.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const DOC_EXTRACT_PORT = "doc-extract";

  const PREP_INJECT_FILES = [
    "doc-extract/prep/unblock-copy.js",
    "doc-extract/prep/hide-chrome.js",
    "doc-extract/prep/expand-all.js",
    "doc-extract/prep/autoscroll.js",
    "doc-extract/prep/run-prep.js",
  ];

  /**
   * @param {chrome.runtime.Port | undefined} port
   * @param {string} stage
   */
  function postExtractProgress(port, stage) {
    if (!port) {
      return;
    }
    try {
      port.postMessage({ type: "extractProgress", stage });
    } catch {
      /* popup closed */
    }
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<void>}
   */
  async function runPrepOnTab(tabId, hostEntry, postProgress) {
    const prep = hostEntry.prep || [];
    if (!prep.length) {
      return;
    }
    postProgress("preparing");
    await chrome.scripting.executeScript({
      target: { tabId },
      files: PREP_INJECT_FILES,
    });
    if (prep.includes("autoscroll")) {
      postProgress("scrolling");
    }
    await chrome.scripting.executeScript({
      target: { tabId },
      func: async (config) => {
        if (!globalThis.__MGDocExtractPrep || !globalThis.__MGDocExtractPrep.runPrep) {
          throw new Error("PREP_NOT_LOADED");
        }
        return globalThis.__MGDocExtractPrep.runPrep(config);
      },
      args: [
        {
          prep,
          hideSelectors: hostEntry.hideSelectors || [],
        },
      ],
    });
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {(stage: string) => void} postProgress
   * @param {object} [options]
   * @returns {Promise<{ blob: Blob, filename: string, multi?: Array<{ blob: Blob, filename: string }> }>}
   */
  async function runEngine(tabId, hostEntry, pageUrl, postProgress, options) {
    const engine = hostEntry.engine;
    if (engine === "api-binary") {
      return MindGraphDocExtract.runApiBinaryEngine(
        tabId,
        hostEntry,
        pageUrl,
        postProgress,
        options,
      );
    }
    if (engine === "canvas-pdf") {
      try {
        return await MindGraphDocExtract.runCanvasPdfEngine(tabId, hostEntry, postProgress);
      } catch (err) {
        const msg = (err && err.message) || String(err);
        if (msg === "CANVAS_EMPTY") {
          return MindGraphDocExtract.runHtml2CanvasPdfEngine(tabId, hostEntry, postProgress);
        }
        if (hostEntry.id === "wenku" && MindGraphDocExtract.guessWenkuReaderPdfUrl(pageUrl)) {
          return MindGraphDocExtract.runApiBinaryEngine(
            tabId,
            hostEntry,
            pageUrl,
            postProgress,
            options,
          );
        }
        throw err;
      }
    }
    if (engine === "html2canvas-pdf") {
      return MindGraphDocExtract.runHtml2CanvasPdfEngine(tabId, hostEntry, postProgress);
    }
    return MindGraphDocExtract.runDomArticleEngine(tabId, hostEntry, postProgress);
  }

  /**
   * @param {{ blob: Blob, filename: string }} item
   * @param {boolean} saveAs
   * @returns {Promise<void>}
   */
  async function downloadExtractBlob(item, saveAs) {
    const prepared = await MindGraphDocExtract.prepareDownloadUrlFromBlob(item.blob);
    postExtractProgress(undefined, "downloading");
    await chrome.downloads.download({
      url: prepared.href,
      filename: item.filename,
      saveAs: Boolean(saveAs),
    });
    MindGraphDocExtract.scheduleDownloadUrlRevoke(prepared.href, prepared.revokeMode);
  }

  /**
   * @param {number} tabId
   * @param {{ progressPort?: chrome.runtime.Port, saveAs?: boolean, smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ ok: boolean, error?: string, filename?: string, host?: object }>}
   */
  async function runDocumentExtract(tabId, options) {
    const progressPort = options && options.progressPort;
    const postProgress = (stage) => postExtractProgress(progressPort, stage);

    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      if (MindGraphShared && MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        return { ok: false, error: "errRestrictedPage" };
      }
      const hostEntry = MindGraphDocExtract.matchHost(pageUrl);
      await runPrepOnTab(tabId, hostEntry, postProgress);
      const result = await runEngine(tabId, hostEntry, pageUrl, postProgress, options || {});
      postProgress("downloading");
      const saveAs = Boolean(options && options.saveAs);
      if (result.multi && result.multi.length > 1) {
        for (const item of result.multi) {
          await downloadExtractBlob(item, saveAs);
        }
        return {
          ok: true,
          filename: result.multi.map((m) => m.filename).join(", "),
          host: hostEntry,
        };
      }
      await downloadExtractBlob(result, saveAs);
      return { ok: true, filename: result.filename, host: hostEntry };
    } catch (err) {
      const message = (err && err.message) || String(err);
      return { ok: false, error: message };
    }
  }

  /**
   * @param {number} tabId
   * @returns {Promise<number|null>}
   */
  async function countCanvasPages(tabId) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => document.querySelectorAll("canvas").length,
      });
      const count = results && results[0] && results[0].result;
      return typeof count === "number" ? count : null;
    } catch {
      return null;
    }
  }

  /**
   * @param {string} pageUrl
   * @param {number} [tabId]
   * @returns {Promise<{ host: object, title?: string, assets?: Array<object>, pageCount?: number|null, smarteduTokenSet?: boolean }>}
   */
  async function previewExtractTarget(pageUrl, tabId) {
    const hostEntry = MindGraphDocExtract.matchHost(pageUrl);
    const out = { host: hostEntry, pageCount: null, smarteduTokenSet: false };

    if (
      tabId &&
      (hostEntry.engine === "canvas-pdf" || hostEntry.engine === "html2canvas-pdf")
    ) {
      out.pageCount = await countCanvasPages(tabId);
    }

    if (hostEntry.id === "smartedu") {
      const stored = await chrome.storage.local.get(["smarteduAccessToken"]);
      out.smarteduTokenSet = Boolean(stored.smarteduAccessToken);
      const parsed = MindGraphDocExtract.parseSmartEduUrl(pageUrl);
      if (parsed) {
        let token = stored.smarteduAccessToken || "";
        if (!token && tabId) {
          token = (await MindGraphDocExtract.resolveSmartEduToken(tabId, "")) || "";
          out.smarteduTokenSet = Boolean(token);
        }
        try {
          const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(token);
          const meta = await MindGraphDocExtract.fetchSmartEduMetadata(
            parsed.detailUrl,
            authHeaders,
          );
          out.title = meta.title;
          out.assets = meta.assets;
        } catch {
          /* token may be required */
        }
      }
    }
    return out;
  }

  MindGraphDocExtract.DOC_EXTRACT_PORT = DOC_EXTRACT_PORT;
  MindGraphDocExtract.runDocumentExtract = runDocumentExtract;
  MindGraphDocExtract.previewExtractTarget = previewExtractTarget;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
