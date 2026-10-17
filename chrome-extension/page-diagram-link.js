/**
 * The one diagram the user just generated, and the page it came from.
 * Session storage survives closing the popup and is cleared when the browser session ends.
 */
(function (global) {
  "use strict";

  const STORAGE_KEY = "lastPageDiagram";
  const LEGACY_MAP_KEY = "pageDiagramLinks";

  /**
   * @param {string | undefined} pageUrl
   * @returns {string}
   */
  function pageDiagramKey(pageUrl) {
    const raw = (pageUrl || "").trim();
    if (!raw) {
      return "";
    }
    try {
      const url = new URL(raw);
      url.hash = "";
      return url.toString();
    } catch {
      return "";
    }
  }

  /**
   * @param {string | undefined} pageUrl
   * @param {string} diagramId
   * @param {string} [presetId]
   * @returns {{ pageUrl: string, diagramId: string, presetId: string } | null}
   */
  function rememberLastDiagram(pageUrl, diagramId, presetId) {
    const key = pageDiagramKey(pageUrl);
    const id = (diagramId || "").trim();
    if (!key || !id) {
      return null;
    }
    return {
      pageUrl: key,
      diagramId: id,
      presetId: (presetId || "").trim(),
    };
  }

  /**
   * @param {object | null | undefined} stored
   * @param {string | undefined} pageUrl
   * @returns {{ diagramId: string, presetId: string } | null}
   */
  function lookupLastDiagram(stored, pageUrl) {
    const key = pageDiagramKey(pageUrl);
    if (!stored || !key || stored.pageUrl !== key) {
      return null;
    }
    if (typeof stored.diagramId !== "string" || !stored.diagramId.trim()) {
      return null;
    }
    return {
      diagramId: stored.diagramId.trim(),
      presetId: typeof stored.presetId === "string" ? stored.presetId : "",
    };
  }

  /**
   * @returns {Promise<{ pageUrl: string, diagramId: string, presetId: string } | null>}
   */
  async function readLastDiagram() {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.session) {
      return null;
    }
    const data = await chrome.storage.session.get(STORAGE_KEY);
    const stored = data && data[STORAGE_KEY];
    return stored && typeof stored === "object" ? stored : null;
  }

  /**
   * @param {string | undefined} pageUrl
   * @param {string} diagramId
   * @param {string} [presetId]
   * @returns {Promise<void>}
   */
  async function savePageDiagram(pageUrl, diagramId, presetId) {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.session) {
      return;
    }
    const next = rememberLastDiagram(pageUrl, diagramId, presetId);
    if (!next) {
      return;
    }
    await chrome.storage.session.set({ [STORAGE_KEY]: next });
    await chrome.storage.session.remove(LEGACY_MAP_KEY);
  }

  /**
   * @param {string | undefined} pageUrl
   * @returns {Promise<{ diagramId: string, presetId: string } | null>}
   */
  async function loadPageDiagram(pageUrl) {
    return lookupLastDiagram(await readLastDiagram(), pageUrl);
  }

  const MindGraphPageDiagramLink = {
    STORAGE_KEY,
    pageDiagramKey,
    rememberLastDiagram,
    lookupLastDiagram,
    savePageDiagram,
    loadPageDiagram,
  };

  global.MindGraphPageDiagramLink = MindGraphPageDiagramLink;
})(typeof window !== "undefined" ? window : globalThis);
