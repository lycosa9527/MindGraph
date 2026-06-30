/**
 * SmartEdu metadata fetch + ti_items walk — mirrors file_reader/smartedu/metadata.py.
 * Keep ti_items walk rules in sync with the file-reader SmartEdu tab.
 * @fileoverview Flatten lesson assets from detail JSON.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const createSmartEduAsset = MindGraphDocExtract.createSmartEduAsset;

  const ALIAS_LABELS = {
    coursewares: "课件",
    lesson_plandesign: "教学设计",
    learning_task: "学习任务单",
  };

  /**
   * @param {string} alias
   * @param {{ localKind?: string }} picked
   * @returns {boolean}
   */
  function isDocumentAsset(alias, picked) {
    if (alias === "micro_lesson_video") {
      return false;
    }
    if (picked && picked.localKind === "m3u8") {
      return false;
    }
    return true;
  }

  /**
   * Pick best download URL from one ti_item (storages may be URL strings or objects).
   * @param {object} item
   * @returns {{ url: string, format: string, localKind: string, rank: number }}
   */
  function pickDownloadFromTiItem(item) {
    const storages = Array.isArray(item.ti_storages) ? item.ti_storages : [];
    const files = Array.isArray(item.ti_files) ? item.ti_files : [];
    const candidates = [];
    const itemFlag = String(item.ti_file_flag || item.ti_format || "").toLowerCase();

    storages.forEach((s) => {
      if (typeof s === "string" && s.trim()) {
        const href = s.trim();
        const flag = itemFlag || (href.includes(".m3u8") ? "m3u8" : "");
        candidates.push(buildCandidate(href, flag));
        return;
      }
      if (!s || typeof s !== "object") {
        return;
      }
      const href = s["href-m3u8"] || s.href || s.url || "";
      if (!href) {
        return;
      }
      const flag = String(s.ti_file_flag || s.format || itemFlag || "").toLowerCase();
      candidates.push(buildCandidate(String(href), flag));
    });

    files.forEach((f) => {
      if (!f || typeof f !== "object") {
        return;
      }
      const href = f.href || f.url || "";
      if (!href) {
        return;
      }
      const flag = String(f.ti_file_flag || f.format || itemFlag || "").toLowerCase();
      candidates.push(buildCandidate(String(href), flag));
    });

    if (!candidates.length) {
      return { url: "", format: "", localKind: "file", rank: 0 };
    }
    candidates.sort((a, b) => b.rank - a.rank);
    return candidates[0];
  }

  /**
   * @param {string} href
   * @param {string} flag
   * @returns {{ url: string, format: string, localKind: string, rank: number }}
   */
  function buildCandidate(href, flag) {
    const lowerFlag = (flag || "").toLowerCase();
    let localKind = "file";
    let rank = 1;
    if (lowerFlag === "pdf" || href.toLowerCase().includes(".pdf")) {
      localKind = "pdf";
      rank = 100;
    } else if (lowerFlag.includes("m3u8") || href.toLowerCase().includes(".m3u8")) {
      localKind = "m3u8";
      rank = lowerFlag === "href-m3u8" ? 90 : lowerFlag.includes("1080") ? 85 : 50;
    }
    return {
      url: href,
      format: lowerFlag || localKind,
      localKind,
      rank,
    };
  }

  /**
   * Pick one asset URL from a national_course_resource block (all ti_items).
   * @param {object} block
   * @returns {{ url: string, format: string, localKind: string }}
   */
  function pickBestFromResourceBlock(block) {
    const tiItems = block && Array.isArray(block.ti_items) ? block.ti_items : [];
    let best = { url: "", format: "", localKind: "file", rank: 0 };
    tiItems.forEach((item) => {
      if (!item || typeof item !== "object") {
        return;
      }
      const picked = pickDownloadFromTiItem(item);
      if (picked.url && picked.rank >= best.rank) {
        best = picked;
      }
    });
    return best;
  }

  /**
   * @param {object} block
   * @returns {string}
   */
  function blockTitle(block) {
    if (block.title) {
      return String(block.title);
    }
    const gt = block.global_title;
    if (gt && typeof gt === "object") {
      return String(gt["zh-CN"] || gt.zh_cn || gt.en || Object.values(gt)[0] || "");
    }
    return "";
  }

  /**
   * @param {object} block
   * @returns {string}
   */
  function blockAlias(block) {
    if (block.resource_type_code) {
      return String(block.resource_type_code);
    }
    if (block.custom_properties && block.custom_properties.alias_name) {
      return String(block.custom_properties.alias_name);
    }
    return "asset";
  }

  /**
   * @param {object} detailJson
   * @returns {Array<object>}
   */
  function extractAssetsFromDetailJson(detailJson) {
    const assets = [];
    const relations = detailJson && detailJson.relations ? detailJson.relations : {};

    Object.keys(relations).forEach((relKey) => {
      const bucket = relations[relKey];
      const items = Array.isArray(bucket) ? bucket : bucket && typeof bucket === "object" ? [bucket] : [];
      items.forEach((block) => {
        if (!block || typeof block !== "object") {
          return;
        }
        const alias = blockAlias(block);
        const picked = pickBestFromResourceBlock(block);
        if (!picked.url || !isDocumentAsset(alias, picked)) {
          return;
        }
        const label = blockTitle(block) || ALIAS_LABELS[alias] || alias;
        assets.push(
          createSmartEduAsset({
            id: String(block.id || block.version_id || `${alias}-${assets.length}`),
            title: label,
            alias,
            format: picked.format,
            downloadUrl: picked.url,
            localKind: picked.localKind,
            selected: true,
          }),
        );
      });
    });

    if (!assets.length && detailJson && detailJson.ti_items) {
      const tiItems = Array.isArray(detailJson.ti_items) ? detailJson.ti_items : [];
      tiItems.forEach((item, idx) => {
        const picked = pickDownloadFromTiItem(item);
        if (!picked.url || !isDocumentAsset(alias, picked)) {
          return;
        }
        const alias = String(item.alias || item.ti_type || `item_${idx}`);
        assets.push(
          createSmartEduAsset({
            id: String(item.id || `root-${idx}`),
            title: String(item.title || ALIAS_LABELS[alias] || alias),
            alias,
            format: picked.format,
            downloadUrl: picked.url,
            localKind: picked.localKind,
            selected: true,
          }),
        );
      });
    }

    return assets;
  }

  /**
   * @param {string} detailUrl
   * @param {Record<string, string>} headers
   * @returns {Promise<{ title: string, assets: Array<object> }>}
   */
  async function fetchSmartEduMetadata(detailUrl, headers) {
    const res = await fetch(detailUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...headers,
      },
    });
    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        await MindGraphDocExtract.clearSmartEduToken();
      }
      throw new Error(`SmartEdu metadata HTTP ${res.status}`);
    }
    const detailJson = await res.json();
    const title =
      (detailJson && (detailJson.title || detailJson.global_title?.["zh-CN"] ||
        detailJson.global_title?.zh_cn)) || "SmartEdu lesson";
    return {
      title: String(title),
      assets: extractAssetsFromDetailJson(detailJson),
    };
  }

  MindGraphDocExtract.extractAssetsFromDetailJson = extractAssetsFromDetailJson;
  MindGraphDocExtract.fetchSmartEduMetadata = fetchSmartEduMetadata;
  MindGraphDocExtract.SMARTEDU_ALIAS_LABELS = ALIAS_LABELS;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
