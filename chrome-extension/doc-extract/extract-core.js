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
          autoscrollStepMs: hostEntry.autoscrollStepMs,
          autoscrollMaxSteps: hostEntry.autoscrollMaxSteps,
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
    if (hostEntry.id === "wenku" && MindGraphDocExtract.guessWenkuReaderPdfUrl(pageUrl)) {
      try {
        return await MindGraphDocExtract.runApiBinaryEngine(
          tabId,
          hostEntry,
          pageUrl,
          postProgress,
          options,
        );
      } catch {
        /* wkretype closed or doc gated — fall back to canvas preview capture */
      }
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
   * @param {object} result
   * @param {object} hostEntry
   * @returns {object}
   */
  function buildExtractSuccessResult(result, hostEntry) {
    const out = {
      ok: true,
      filename: result.filename,
      host: hostEntry,
    };
    if (result.extractNotice && result.extractNotice.key) {
      out.notice = result.extractNotice.key;
      out.noticeArgs = [result.extractNotice.pageCount || String(result.pageCount || "")];
    }
    return out;
  }

  /**
   * @param {number} tabId
   * @param {{ progressPort?: chrome.runtime.Port, saveAs?: boolean, smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ ok: boolean, error?: string, filename?: string, host?: object, notice?: string, noticeArgs?: string[] }>}
   */
  async function runDocumentExtract(tabId, options) {
    const progressPort = options && options.progressPort;
    const postProgress = (stage) => postExtractProgress(progressPort, stage);
    let hostEntry = null;

    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      if (MindGraphShared && MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        return { ok: false, error: "errRestrictedPage" };
      }
      hostEntry = MindGraphDocExtract.matchHost(pageUrl);
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
      return buildExtractSuccessResult(result, hostEntry);
    } catch (err) {
      const message = (err && err.message) || String(err);
      const errorKey = MindGraphDocExtract.resolveExtractErrorKey
        ? MindGraphDocExtract.resolveExtractErrorKey(message, hostEntry)
        : message;
      return { ok: false, error: errorKey };
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
   * @param {number | undefined} tabId
   * @param {string} [fallbackUrl]
   * @returns {Promise<string>}
   */
  async function resolveTabPageUrl(tabId, fallbackUrl) {
    if (typeof tabId === "number" && tabId > 0) {
      try {
        const tab = await chrome.tabs.get(tabId);
        if (tab.url && MindGraphShared && !MindGraphShared.isRestrictedTabUrl(tab.url)) {
          return tab.url;
        }
      } catch {
        /* tab closed or inaccessible */
      }
    }
    return typeof fallbackUrl === "string" ? fallbackUrl : "";
  }

  /**
   * @param {string} pageUrl
   * @param {number} [tabId]
   * @returns {Promise<{ host: object, title?: string, assets?: Array<object>, pageCount?: number|null, smarteduTokenSet?: boolean, pageUrl?: string }>}
   */
  async function previewExtractTarget(pageUrl, tabId) {
    const resolvedUrl = await resolveTabPageUrl(tabId, pageUrl);
    const hostEntry = MindGraphDocExtract.matchHost(resolvedUrl);
    const out = { host: hostEntry, pageCount: null, smarteduTokenSet: false, pageUrl: resolvedUrl };

    if (
      tabId &&
      (hostEntry.engine === "canvas-pdf" || hostEntry.engine === "html2canvas-pdf")
    ) {
      out.pageCount = await countCanvasPages(tabId);
    }

    if (hostEntry.id === "smartedu") {
      const token = await MindGraphExtensionStorage.getSmartEduTokenIfFresh();
      out.smarteduTokenSet = Boolean(token);
      const parsed = MindGraphDocExtract.parseSmartEduUrl(resolvedUrl);
      if (parsed) {
        let activeToken = token || "";
        if (!activeToken && tabId) {
          activeToken = (await MindGraphDocExtract.resolveSmartEduToken(tabId, "")) || "";
          out.smarteduTokenSet = Boolean(activeToken);
        }
        try {
          const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(activeToken);
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
  MindGraphDocExtract.resolveTabPageUrl = resolveTabPageUrl;
  MindGraphDocExtract.runDocumentExtract = runDocumentExtract;
  MindGraphDocExtract.previewExtractTarget = previewExtractTarget;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
