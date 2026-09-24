/**
 * Thin host wrapper — canvas-pdf host hide-selector reference.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.DOCIN_HOST_ID = "docin";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
