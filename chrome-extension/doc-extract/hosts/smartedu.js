/**
 * Thin host wrapper — api-binary lesson host routes to doc-extract/smartedu/.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.SMARTEDU_HOST_ID = "smartedu";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
