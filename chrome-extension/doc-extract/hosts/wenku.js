/**
 * Thin host wrapper — canvas-pdf host prep hooks.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.WENKU_HOST_ID = "wenku";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
