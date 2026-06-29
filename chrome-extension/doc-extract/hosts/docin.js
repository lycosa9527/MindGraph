/**
 * Thin host wrapper — 437609 docin_ele hide list reference.
 */
(function (global) {
  "use strict";
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  MindGraphDocExtract.DOCIN_HOST_ID = "docin";
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
