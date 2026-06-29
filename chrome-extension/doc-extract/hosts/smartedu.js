/**
 * Thin host wrapper — SmartEdu routes to doc-extract/smartedu/.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.SMARTEDU_HOST_ID = "smartedu";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
