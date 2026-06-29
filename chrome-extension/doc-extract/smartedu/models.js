/**
 * SmartEdu asset model — mirrors clients/file-reader/file_reader/smartedu/models.py.
 * Keep field names in sync with the file-reader SmartEdu tab.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @typedef {object} SmartEduAsset
   * @property {string} id
   * @property {string} title
   * @property {string} alias
   * @property {string} format
   * @property {string} downloadUrl
   * @property {boolean} selected
   * @property {string} [localKind] pdf | mp4 | m3u8 | office
   */

  /**
   * @param {object} raw
   * @returns {SmartEduAsset}
   */
  function createSmartEduAsset(raw) {
    return {
      id: String(raw.id || ""),
      title: String(raw.title || "Untitled"),
      alias: String(raw.alias || raw.title || ""),
      format: String(raw.format || ""),
      downloadUrl: String(raw.downloadUrl || ""),
      selected: raw.selected !== false,
      localKind: raw.localKind ? String(raw.localKind) : undefined,
    };
  }

  MindGraphDocExtract.createSmartEduAsset = createSmartEduAsset;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
