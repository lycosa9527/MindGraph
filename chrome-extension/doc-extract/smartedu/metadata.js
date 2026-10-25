/**
 * Lesson metadata fetch + ti_items walk — mirrors file_reader/smartedu/metadata.py.
 * Keep ti_items walk rules in sync with the file-reader lesson-platform tab.
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
        const candidate = buildCandidate(href, flag);
        candidate.pageCount = pageCountFromTiItem(item);
        candidates.push(candidate);
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
      const candidate = buildCandidate(String(href), flag);
      candidate.pageCount = pageCountFromTiItem(item);
      candidates.push(candidate);
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
      const candidate = buildCandidate(String(href), flag);
      candidate.pageCount = pageCountFromTiItem(item);
      candidates.push(candidate);
    });

    if (!candidates.length) {
      return { url: "", format: "", localKind: "file", rank: 0 };
    }
    candidates.sort((a, b) => b.rank - a.rank);
    return candidates[0];
  }

  /**
   * @param {object} item
   * @returns {number}
   */
  function pageCountFromTiItem(item) {
    const reqs = item && item.custom_properties && item.custom_properties.requirements;
    if (!Array.isArray(reqs)) {
      return 0;
    }
    const hit = reqs.find((row) => row && row.name === "pagesize");
    const count = hit ? Number(hit.value) : 0;
    return Number.isFinite(count) && count > 0 ? count : 0;
  }

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
   * Stable resource id for dedup when the same block appears under multiple relation keys.
   * @param {object} block
   * @returns {string}
   */
  function blockResourceId(block) {
    if (block.id) {
      return String(block.id);
    }
    if (block.version_id) {
      return String(block.version_id);
    }
    return globalResourceId(block);
  }

  /**
   * @param {object} block
   * @returns {string}
   */
  function globalResourceId(block) {
    const globalId = block.custom_properties && block.custom_properties.global_resource_id;
    return globalId ? String(globalId) : "";
  }

  /**
   * Period name lives on global_title; block.title is only the file type (课件, 教学设计).
   * @param {object} block
   * @returns {string}
   */
  function blockGlobalTitle(block) {
    const gt = block.global_title;
    if (typeof gt === "string") {
      return gt.trim();
    }
    if (gt && typeof gt === "object") {
      return String(gt["zh-CN"] || gt.zh_cn || gt.en || "").trim();
    }
    return "";
  }

  /**
   * Normalize download URL to a path-only key (CDN host may differ for the same file).
   * @param {string} url
   * @returns {string}
   */
  function downloadUrlDedupeKey(url) {
    if (!url) {
      return "";
    }
    try {
      return new URL(url).pathname.toLowerCase();
    } catch {
      return url.trim().toLowerCase();
    }
  }

  /**
   * Same file can show up under a second relation key with a different block id.
   * Match on resource id, global id, or download path.
   * @param {Set<string>} seenKeys
   * @param {string} resourceId
   * @param {string} globalId
   * @param {string} downloadUrl
   * @returns {boolean} true when this asset should be skipped as a duplicate
   */
  function claimDuplicateAsset(seenKeys, resourceId, globalId, downloadUrl) {
    const keys = [];
    if (resourceId) {
      keys.push(`id:${resourceId}`);
    }
    if (globalId && globalId !== resourceId) {
      keys.push(`gid:${globalId}`);
    }
    const urlKey = downloadUrlDedupeKey(downloadUrl);
    if (urlKey) {
      keys.push(`url:${urlKey}`);
    }
    if (!keys.length) {
      return false;
    }
    if (keys.some((key) => seenKeys.has(key))) {
      return true;
    }
    keys.forEach((key) => seenKeys.add(key));
    return false;
  }

  /**
   * @param {string} ref
   * @returns {{ relKey: string, indexes: number[] | null } | null}
   */
  function parseRelationRef(ref) {
    const match = /^\$\.relations\.([A-Za-z0-9_.]+)\[(\*|[\d,\s]+)\]$/.exec(String(ref || ""));
    if (!match) {
      return null;
    }
    if (match[2] === "*") {
      return { relKey: match[1], indexes: null };
    }
    const indexes = match[2]
      .split(",")
      .map((part) => Number(part.trim()))
      .filter((num) => Number.isInteger(num) && num >= 0);
    return { relKey: match[1], indexes };
  }

  /**
   * Map relation-array indexes to 第一课时 / 第二课时 from resource_structure.
   * @param {object} detailJson
   * @returns {{ byIndex: Map<string, string>, wildcard: Map<string, string> }}
   */
  function lessonGroupIndex(detailJson) {
    const groups =
      detailJson &&
      detailJson.resource_structure &&
      Array.isArray(detailJson.resource_structure.relations)
        ? detailJson.resource_structure.relations
        : [];
    const byIndex = new Map();
    const wildcard = new Map();
    groups.forEach((group) => {
      const title = group && group.title ? String(group.title).trim() : "";
      if (!title) {
        return;
      }
      const refs = Array.isArray(group.res_ref) ? group.res_ref : [];
      refs.forEach((ref) => {
        const parsed = parseRelationRef(ref);
        if (!parsed) {
          return;
        }
        if (parsed.indexes === null) {
          wildcard.set(parsed.relKey, title);
          return;
        }
        parsed.indexes.forEach((index) => {
          byIndex.set(`${parsed.relKey}:${index}`, title);
        });
      });
    });
    return { byIndex, wildcard };
  }

  /**
   * @param {{ byIndex: Map<string, string>, wildcard: Map<string, string> }} groups
   * @param {string} relKey
   * @param {number} index
   * @returns {string}
   */
  function groupTitleFor(groups, relKey, index) {
    const exact = groups.byIndex.get(`${relKey}:${index}`);
    if (exact) {
      return exact;
    }
    return groups.wildcard.get(relKey) || "";
  }

  /**
   * Two class hours reuse the same type name (课件). Prefix the hour so the
   * checklist and download names stay distinct.
   * @param {Array<{ shortTitle: string, globalTitle: string, groupTitle: string, asset: object }>} rows
   * @returns {Array<object>}
   */
  function labelRepeatedAssets(rows) {
    const groupTitles = new Set(rows.map((row) => row.groupTitle).filter(Boolean));
    const globalsByShort = new Map();
    rows.forEach((row) => {
      const bucket = globalsByShort.get(row.shortTitle) || [];
      bucket.push(row.globalTitle);
      globalsByShort.set(row.shortTitle, bucket);
    });
    return rows.map((row) => {
      let title = row.shortTitle;
      if (groupTitles.size > 1 && row.groupTitle) {
        title = `${row.groupTitle} · ${row.shortTitle}`;
      } else {
        const variants = new Set((globalsByShort.get(row.shortTitle) || []).filter(Boolean));
        if (variants.size > 1 && row.globalTitle && row.globalTitle !== row.shortTitle) {
          title = `${row.globalTitle} · ${row.shortTitle}`;
        }
      }
      return createSmartEduAsset({ ...row.asset, title });
    });
  }

  /**
   * @param {object} detailJson
   * @returns {Array<object>}
   */
  function extractAssetsFromDetailJson(detailJson) {
    const rows = [];
    const seenKeys = new Set();
    const relations = detailJson && detailJson.relations ? detailJson.relations : {};
    const groups = lessonGroupIndex(detailJson);

    /**
     * @param {object} fields
     * @param {string} shortTitle
     * @param {string} globalTitle
     * @param {string} groupTitle
     */
    function pushRow(fields, shortTitle, globalTitle, groupTitle) {
      rows.push({
        shortTitle,
        globalTitle,
        groupTitle,
        asset: fields,
      });
    }

    Object.keys(relations).forEach((relKey) => {
      const bucket = relations[relKey];
      const items = Array.isArray(bucket) ? bucket : bucket && typeof bucket === "object" ? [bucket] : [];
      items.forEach((block, index) => {
        if (!block || typeof block !== "object") {
          return;
        }
        const alias = blockAlias(block);
        const picked = pickBestFromResourceBlock(block);
        if (!picked.url || !isDocumentAsset(alias, picked)) {
          return;
        }
        if (claimDuplicateAsset(seenKeys, blockResourceId(block), globalResourceId(block), picked.url)) {
          return;
        }
        const label = blockTitle(block) || ALIAS_LABELS[alias] || alias;
        pushRow(
          {
            id: String(block.id || block.version_id || `${alias}-${rows.length}`),
            alias,
            format: picked.format,
            downloadUrl: picked.url,
            localKind: picked.localKind,
            pageCount: picked.pageCount || 0,
            selected: true,
          },
          label,
          blockGlobalTitle(block),
          groupTitleFor(groups, relKey, index),
        );
      });
    });

    if (!rows.length && detailJson && detailJson.ti_items) {
      const tiItems = Array.isArray(detailJson.ti_items) ? detailJson.ti_items : [];
      tiItems.forEach((item, idx) => {
        const alias = String(item.alias || item.ti_type || `item_${idx}`);
        const picked = pickDownloadFromTiItem(item);
        if (!picked.url || !isDocumentAsset(alias, picked)) {
          return;
        }
        const itemId = item.id ? String(item.id) : "";
        if (claimDuplicateAsset(seenKeys, itemId, "", picked.url)) {
          return;
        }
        const label = String(item.title || ALIAS_LABELS[alias] || alias);
        pushRow(
          {
            id: String(item.id || `root-${idx}`),
            alias,
            format: picked.format,
            downloadUrl: picked.url,
            localKind: picked.localKind,
            pageCount: picked.pageCount || 0,
            selected: true,
          },
          label,
          "",
          "",
        );
      });
    }

    return labelRepeatedAssets(rows);
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
