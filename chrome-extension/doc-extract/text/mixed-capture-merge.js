/**
 * Merge visible page markdown with file/PDF extracts (mixed host content).
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const SHELL_MIN_CHARS = 120;
  const SHELL_SECTION_TITLE = "Web page";
  const OVERLAP_PROBE_CHARS = 240;

  /**
   * @param {string} haystack
   * @param {string} needle
   * @returns {boolean}
   */
  function textMostlyContained(haystack, needle) {
    const big = (haystack || "").trim();
    const small = (needle || "").trim();
    if (!big || !small) {
      return false;
    }
    const probe = small.slice(0, Math.min(OVERLAP_PROBE_CHARS, small.length));
    return big.includes(probe);
  }

  /**
   * @param {string} shellMarkdown
   * @param {string} documentMarkdown
   * @param {number} maxChars
   * @param {string} [sectionTitle]
   * @returns {string}
   */
  function mergePageShellWithDocuments(shellMarkdown, documentMarkdown, maxChars, sectionTitle) {
    const shell = (shellMarkdown || "").trim();
    const docs = (documentMarkdown || "").trim();
    const title = (sectionTitle || SHELL_SECTION_TITLE).trim() || SHELL_SECTION_TITLE;
    if (!shell || shell.length < SHELL_MIN_CHARS) {
      return docs;
    }
    if (!docs) {
      return shell;
    }
    if (textMostlyContained(docs, shell)) {
      return docs;
    }
    const shellBlock = `## ${title}\n\n${shell}`;
    let combined = `${shellBlock}\n\n${docs}`;
    if (!maxChars || combined.length <= maxChars) {
      return combined.trim();
    }
    let budget = Math.max(0, maxChars - docs.length - 12);
    if (budget <= SHELL_MIN_CHARS) {
      return docs.slice(0, maxChars).trim();
    }
    const trimmedShell = shell.slice(0, budget).trim();
    combined = `## ${title}\n\n${trimmedShell}\n\n…\n\n${docs}`;
    if (combined.length > maxChars) {
      return combined.slice(0, maxChars - 3).trim() + "\n\n…";
    }
    return combined.trim();
  }

  /**
   * @param {string} localText
   * @param {string} ocrText
   * @param {number} [minChars]
   * @returns {string}
   */
  function mergePdfTextAndOcr(localText, ocrText, minChars) {
    const floor = typeof minChars === "number" && minChars > 0 ? minChars : 20;
    const local = (localText || "").trim();
    const ocr = (ocrText || "").trim();
    if (local.length >= floor && ocr.length >= floor) {
      if (textMostlyContained(ocr, local) || textMostlyContained(local, ocr)) {
        return ocr.length >= local.length ? ocr : local;
      }
      return `${local}\n\n${ocr}`.trim();
    }
    if (local.length >= floor) {
      return local;
    }
    if (ocr.length >= floor) {
      return ocr;
    }
    return ocr.length > local.length ? ocr : local;
  }

  MindGraphDocExtract.mergePageShellWithDocuments = mergePageShellWithDocuments;
  MindGraphDocExtract.mergePdfTextAndOcr = mergePdfTextAndOcr;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
