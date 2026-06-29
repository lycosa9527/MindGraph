/**
 * Thin host wrapper — 437609 bdwk prep hooks for wenku.baidu.com.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.WENKU_HOST_ID = "wenku";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
