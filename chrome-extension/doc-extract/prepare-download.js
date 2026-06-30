/**
 * Blob download URL preparation — delegates to shared offscreen-blobs module.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  MindGraphDocExtract.prepareDownloadUrlFromBlob = MindGraphOffscreenBlobs.prepareDownloadUrlFromBlob;
  MindGraphDocExtract.scheduleDownloadUrlRevoke = MindGraphOffscreenBlobs.scheduleDownloadUrlRevoke;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
