/**
 * Lesson PDFs → combined markdown for MindMate.
 * Downloads PDF blobs in memory (no disk). pdf.js reads a text layer;
 * image-only transcodes are OCR'd by the MindGraph account.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const PDF_MAX_PAGES = 120;
  const PDF_TEXT_MIN_CHARS = 20;
  const OCR_PAGES_PER_ASSET = 4;
  const OCR_PAGE_BUDGET = 12;
  const OCR_ALIAS_RANK = {
    lesson_plandesign: 0,
    learning_task: 1,
    after_class_exercise: 2,
    coursewares: 3,
  };

  /**
   * @param {Array<object>} assets
   * @returns {Array<object>}
   */
  function filterSmartEduPdfAssets(assets) {
    if (!Array.isArray(assets)) {
      return [];
    }
    return assets.filter((asset) => {
      if (!asset || asset.selected === false) {
        return false;
      }
      if (asset.localKind === "pdf" || asset.format === "pdf") {
        return true;
      }
      const url = String(asset.downloadUrl || "").toLowerCase();
      return url.includes(".pdf");
    });
  }

  /**
   * Teaching plans and worksheets before slide decks. Image PDFs need OCR,
   * and the page budget should be spent on the text-heavy files first.
   * @param {object} asset
   * @returns {number}
   */
  function smartEduOcrRank(asset) {
    const alias = asset && asset.alias ? String(asset.alias) : "";
    if (Object.prototype.hasOwnProperty.call(OCR_ALIAS_RANK, alias)) {
      return OCR_ALIAS_RANK[alias];
    }
    return 4;
  }

  /**
   * @param {Array<object>} assets
   * @returns {Array<object>}
   */
  function orderSmartEduAssetsForOcr(assets) {
    return assets
      .map((asset, index) => ({ asset, index }))
      .sort((left, right) => {
        const rankDiff = smartEduOcrRank(left.asset) - smartEduOcrRank(right.asset);
        if (rankDiff !== 0) {
          return rankDiff;
        }
        return left.index - right.index;
      })
      .map((entry) => entry.asset);
  }

  /**
   * @param {number} pagesLeft
   * @param {number} [pageCount]
   * @returns {number}
   */
  function smartEduOcrPageCap(pagesLeft, pageCount) {
    if (!pagesLeft || pagesLeft <= 0) {
      return 0;
    }
    const known = Number(pageCount) > 0 ? Number(pageCount) : OCR_PAGES_PER_ASSET;
    return Math.min(OCR_PAGES_PER_ASSET, pagesLeft, known);
  }

  /**
   * @param {string} localText
   * @param {string} ocrText
   * @returns {string}
   */
  function chooseSmartEduPdfText(localText, ocrText) {
    const merge = MindGraphDocExtract.mergePdfTextAndOcr;
    if (typeof merge === "function") {
      const merged = merge(localText, ocrText, PDF_TEXT_MIN_CHARS).trim();
      return merged.length >= PDF_TEXT_MIN_CHARS ? merged : "";
    }
    const local = (localText || "").trim();
    if (local.length >= PDF_TEXT_MIN_CHARS) {
      return local;
    }
    const ocr = (ocrText || "").trim();
    if (ocr.length >= PDF_TEXT_MIN_CHARS) {
      return ocr;
    }
    return "";
  }

  /**
   * Vision OCR runs only for image pages that pdf.js could not read.
   * @param {string} localText
   * @param {boolean} imageBased
   * @returns {boolean}
   */
  function smartEduShouldRequestOcr(localText, imageBased) {
    if (chooseSmartEduPdfText(localText, "")) {
      return false;
    }
    return Boolean(imageBased);
  }

  /**
   * @param {string} lessonTitle
   * @param {string} pageUrl
   * @param {Array<{ title: string, text: string }>} sections
   * @param {number} maxChars
   * @returns {string}
   */
  function combineSmartEduLessonMarkdown(lessonTitle, pageUrl, sections, maxChars) {
    const safeTitle = (lessonTitle || "SmartEdu lesson").trim();
    const safeUrl = (pageUrl || "").trim();
    const header = `# ${safeTitle}\n\n> ${safeUrl}\n\n`;
    const bodyParts = sections
      .filter((section) => section && section.text && section.text.trim())
      .map((section) => `## ${section.title}\n\n${section.text.trim()}`);
    let body = bodyParts.join("\n\n");
    let combined = header + body;
    if (!maxChars || combined.length <= maxChars) {
      return combined.trim();
    }
    let budget = Math.max(0, maxChars - header.length - 10);
    if (budget <= 0) {
      return `${header.trim()}\n\n…`.slice(0, maxChars);
    }
    const trimmedSections = [];
    for (const section of sections) {
      if (!section || !section.text) {
        continue;
      }
      const block = `## ${section.title}\n\n${section.text.trim()}`;
      if (block.length <= budget) {
        trimmedSections.push(block);
        budget -= block.length + 2;
        continue;
      }
      if (budget > 40) {
        const sliceLen = budget - section.title.length - 10;
        trimmedSections.push(`## ${section.title}\n\n${section.text.trim().slice(0, sliceLen)}\n\n…`);
      }
      break;
    }
    body = trimmedSections.join("\n\n");
    combined = header + body;
    if (combined.length > maxChars) {
      return `${combined.slice(0, maxChars - 3).trim()}\n\n…`;
    }
    return combined.trim();
  }

  /**
   * @returns {{ log: Function } | null}
   */
  function captureDebug() {
    const root = global.MindGraphMindMate;
    return root && root.captureDebug ? root.captureDebug : null;
  }

  /**
   * @returns {{ publishCaptureProgress: Function } | null}
   */
  function captureProgress() {
    const root = global.MindGraphMindMate;
    return root && root.captureProgress ? root.captureProgress : null;
  }

  /**
   * @param {number} tabId
   * @param {string} pageUrl
   * @param {number} maxChars
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ title: string, url: string, markdown: string, source: string } | { ok: false, error: string } | null>}
   */
  async function trySmartEduPdfMarkdown(tabId, pageUrl, maxChars, options) {
    const dbg = captureDebug();
    if (typeof MindGraphDocExtract.parseSmartEduUrl !== "function") {
      if (dbg) {
        dbg.log("smartedu.parse", "parseSmartEduUrl missing");
      }
      return null;
    }
    const parsed = MindGraphDocExtract.parseSmartEduUrl(pageUrl);
    if (!parsed) {
      if (dbg) {
        dbg.log("smartedu.parse", "URL not a SmartEdu lesson detail page", { pageUrl });
      }
      return null;
    }
    if (dbg) {
      dbg.log("smartedu.parse", "parsed lesson URL", {
        kind: parsed.kind,
        activityId: parsed.activityId,
        detailUrl: parsed.detailUrl,
      });
    }

    const token = await MindGraphDocExtract.resolveSmartEduToken(
      tabId,
      options && options.smarteduToken,
    );
    if (!token) {
      if (dbg) {
        dbg.log("smartedu.token", "no SmartEdu token (login/sync required)");
      }
      return { ok: false, error: "errExtractSmartEduLogin" };
    }
    if (dbg) {
      dbg.log("smartedu.token", "token resolved", { tokenPresent: true });
    }

    let meta = null;
    try {
      const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(token);
      meta = await MindGraphDocExtract.fetchSmartEduMetadata(parsed.detailUrl, authHeaders);
    } catch (err) {
      if (dbg) {
        dbg.log("smartedu.metadata", "metadata fetch failed", {
          message: err instanceof Error ? err.message : "unknown",
        });
      }
      return { ok: false, error: "errExtractSmartEduLogin" };
    }
    if (dbg) {
      dbg.log("smartedu.metadata", "metadata loaded", {
        title: meta && meta.title,
        assetCount: meta && meta.assets ? meta.assets.length : 0,
      });
    }

    let assets = filterSmartEduPdfAssets(meta.assets);
    if (options && Array.isArray(options.smarteduAssets) && options.smarteduAssets.length) {
      const selectedIds = new Set(
        options.smarteduAssets.filter((asset) => asset.selected !== false).map((asset) => String(asset.id)),
      );
      assets = assets.filter((asset) => selectedIds.has(String(asset.id)));
      if (dbg) {
        dbg.log("smartedu.assets", "filtered by selected asset ids", { count: assets.length });
      }
    }
    if (!assets.length) {
      if (dbg) {
        dbg.log("smartedu.assets", "no PDF assets after filter", {
          rawAssetCount: meta && meta.assets ? meta.assets.length : 0,
        });
      }
      return { ok: false, error: "errExtractSmartEduNoFiles" };
    }
    assets = orderSmartEduAssetsForOcr(assets);
    if (dbg) {
      dbg.log("smartedu.assets", "PDF assets to download", {
        count: assets.length,
        titles: assets.map((asset) => asset.title || asset.alias || asset.id),
      });
    }

    const prog = captureProgress();
    if (prog) {
      await prog.publishCaptureProgress({
        phase: "smartedu_detected",
        hostId: "smartedu",
        messageKey: "mindmatePageContextSmarteduAssets",
        messageSubs: [String(assets.length)],
        assetTotal: assets.length,
        assetDone: 0,
      });
    }

    const authHeaders = MindGraphDocExtract.buildSmartEduAuthHeaders(token);
    const extractPdf =
      typeof MindGraphDocExtract.extractPdfBlobTextWithFallback === "function"
        ? MindGraphDocExtract.extractPdfBlobTextWithFallback
        : typeof MindGraphDocExtract.extractBlobTextInTab === "function"
          ? MindGraphDocExtract.extractBlobTextInTab
          : MindGraphDocExtract.extractPdfBlobTextInTab;
    if (!extractPdf) {
      return null;
    }

    const perAssetChars = Math.max(400, Math.floor(maxChars / Math.max(1, assets.length)));
    const maxPagesPerAsset = Math.min(
      80,
      Math.max(8, Math.floor(PDF_MAX_PAGES / Math.max(1, assets.length))),
    );

    /** @type {Array<{ title: string, text: string }>} */
    const sections = [];
    let ocrPagesLeft = OCR_PAGE_BUDGET;
    for (let assetIndex = 0; assetIndex < assets.length; assetIndex += 1) {
      const asset = assets[assetIndex];
      const assetTitle = asset.title || asset.alias || "document";
      if (prog) {
        await prog.publishCaptureProgress({
          phase: "smartedu_download",
          hostId: "smartedu",
          messageKey: "mindmatePageContextSmarteduDownloading",
          messageSubs: [String(assetIndex + 1), String(assets.length), assetTitle],
          assetTotal: assets.length,
          assetDone: assetIndex,
          assetTitle,
        });
      }
      try {
        const downloaded = await MindGraphDocExtract.downloadSmartEduAsset(asset, token, authHeaders);
        if (dbg) {
          dbg.log("smartedu.download", "blob downloaded", {
            title: assetTitle,
            bytes: downloaded && downloaded.blob ? downloaded.blob.size : 0,
          });
        }
        if (prog) {
          await prog.publishCaptureProgress({
            phase: "smartedu_extract",
            hostId: "smartedu",
            messageKey: "mindmatePageContextSmarteduExtracting",
            messageSubs: [String(assetIndex + 1), String(assets.length), assetTitle],
            assetTotal: assets.length,
            assetDone: assetIndex + 1,
            assetTitle,
          });
        }
        let localText = "";
        let imageBased = false;
        let detectedPages = asset.pageCount || 0;
        const classifyPdf =
          typeof MindGraphDocExtract.classifyPdfBlobWithFallback === "function"
            ? MindGraphDocExtract.classifyPdfBlobWithFallback
            : null;
        try {
          if (classifyPdf) {
            const classified = await classifyPdf(
              tabId,
              downloaded.blob,
              maxPagesPerAsset,
              perAssetChars,
            );
            localText = classified && classified.text ? classified.text : "";
            imageBased = Boolean(classified && classified.imageBased);
            if (classified && classified.pageCount) {
              detectedPages = classified.pageCount;
            }
            if (dbg) {
              dbg.log("smartedu.classify", "PDF classified", {
                title: assetTitle,
                chars: localText.trim().length,
                imageBased,
                pageCount: detectedPages,
              });
            }
          } else {
            localText = await extractPdf(tabId, downloaded.blob, maxPagesPerAsset, perAssetChars);
          }
        } catch (extractErr) {
          if (dbg) {
            dbg.log("smartedu.extract", "PDF extract failed", {
              title: assetTitle,
              message: extractErr instanceof Error ? extractErr.message : "unknown",
            });
          }
        }
        let text = chooseSmartEduPdfText(localText, "");
        const pageCap = smartEduOcrPageCap(ocrPagesLeft, detectedPages);
        const ocrPdf =
          typeof MindGraphDocExtract.ocrSmartEduPdfBlob === "function"
            ? MindGraphDocExtract.ocrSmartEduPdfBlob
            : null;
        if (smartEduShouldRequestOcr(localText, imageBased) && pageCap > 0 && ocrPdf && downloaded && downloaded.blob) {
          if (prog) {
            await prog.publishCaptureProgress({
              phase: "smartedu_ocr",
              hostId: "smartedu",
              messageKey: "mindmatePageContextSmarteduOcr",
              messageSubs: [String(assetIndex + 1), String(assets.length), assetTitle],
              assetTotal: assets.length,
              assetDone: assetIndex,
              assetTitle,
            });
          }
          ocrPagesLeft -= pageCap;
          try {
            const ocrText = await ocrPdf(downloaded.blob, pageCap, assetTitle);
            text = chooseSmartEduPdfText("", ocrText);
          } catch (ocrErr) {
            if (dbg) {
              dbg.log("smartedu.ocr", "OCR call failed", {
                title: assetTitle,
                message: ocrErr instanceof Error ? ocrErr.message : "unknown",
              });
            }
          }
        }
        if (text) {
          if (dbg) {
            dbg.log("smartedu.extract", "PDF text extracted", {
              title: assetTitle,
              chars: text.length,
            });
          }
          sections.push({
            title: assetTitle,
            text,
          });
        } else if (dbg) {
          dbg.log("smartedu.extract", "PDF text too short", {
            title: assetTitle,
            chars: localText ? localText.trim().length : 0,
            imageBased,
            ocrPagesLeft,
          });
        }
      } catch (err) {
        if (dbg) {
          dbg.log("smartedu.download", "asset failed", {
            title: assetTitle,
            message: err instanceof Error ? err.message : "unknown",
          });
        }
      }
    }

    if (!sections.length) {
      if (dbg) {
        dbg.log("smartedu.finish", "no sections with extractable text");
      }
      return { ok: false, error: "errMindMatePageEmpty" };
    }

    const lessonTitle = meta.title || tabTitleFallback(pageUrl);
    const markdown = combineSmartEduLessonMarkdown(lessonTitle, pageUrl, sections, maxChars);
    if (!markdown || markdown.length < 40) {
      if (dbg) {
        dbg.log("smartedu.finish", "combined markdown too short", { markdownLen: markdown ? markdown.length : 0 });
      }
      return { ok: false, error: "errMindMatePageEmpty" };
    }
    if (dbg) {
      dbg.log("smartedu.finish", "combined markdown ready", {
        markdownLen: markdown.length,
        sectionCount: sections.length,
      });
    }
    return {
      title: lessonTitle,
      url: pageUrl,
      markdown,
      source: "smartedu-pdf",
      assetTotal: sections.length,
    };
  }

  /**
   * @param {string} pageUrl
   * @returns {string}
   */
  function tabTitleFallback(pageUrl) {
    try {
      return decodeURIComponent(new URL(pageUrl).searchParams.get("activityId") || "SmartEdu lesson");
    } catch {
      return "SmartEdu lesson";
    }
  }

  MindGraphDocExtract.filterSmartEduPdfAssets = filterSmartEduPdfAssets;
  MindGraphDocExtract.orderSmartEduAssetsForOcr = orderSmartEduAssetsForOcr;
  MindGraphDocExtract.smartEduOcrPageCap = smartEduOcrPageCap;
  MindGraphDocExtract.chooseSmartEduPdfText = chooseSmartEduPdfText;
  MindGraphDocExtract.smartEduShouldRequestOcr = smartEduShouldRequestOcr;
  MindGraphDocExtract.combineSmartEduLessonMarkdown = combineSmartEduLessonMarkdown;
  MindGraphDocExtract.trySmartEduPdfMarkdown = trySmartEduPdfMarkdown;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
