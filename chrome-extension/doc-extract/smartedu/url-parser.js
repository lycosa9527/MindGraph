/**
 * SmartEdu URL parser — mirrors clients/file-reader/file_reader/smartedu/url_parser.py.
 * Keep URL templates in sync with the file-reader SmartEdu tab.
 * @fileoverview Map SmartEdu page URLs to detail JSON API templates.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /** @typedef {{ kind: string, activityId: string, detailUrl: string }} SmartEduParsedUrl */

  const DETAIL_TEMPLATES = {
    class_activity:
      "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/national_lesson/resources/details/{activityId}.json",
    national_lesson:
      "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/national_lesson/resources/details/{activityId}.json",
    tch_material:
      "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/details/{activityId}.json",
    prepare_detail:
      "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare/detail/{activityId}.json",
  };

  /**
   * @param {string} pageUrl
   * @returns {SmartEduParsedUrl | null}
   */
  function parseSmartEduUrl(pageUrl) {
    if (!pageUrl || typeof pageUrl !== "string") {
      return null;
    }
    let parsed;
    try {
      parsed = new URL(pageUrl);
    } catch {
      return null;
    }
    if (!parsed.hostname.toLowerCase().includes("smartedu.cn")) {
      return null;
    }
    const activityId =
      parsed.searchParams.get("activityId") ||
      parsed.searchParams.get("contentId") ||
      parsed.searchParams.get("resourceId") ||
      "";
    if (!activityId) {
      return null;
    }
    const path = parsed.pathname.toLowerCase();
    let kind = "class_activity";
    if (path.includes("tchmaterial") || path.includes("tch_material")) {
      kind = "tch_material";
    } else if (path.includes("prepare")) {
      kind = "prepare_detail";
    } else if (path.includes("classactivity") || path.includes("syncclassroom")) {
      kind = "class_activity";
    }
    const template = DETAIL_TEMPLATES[kind] || DETAIL_TEMPLATES.class_activity;
    return {
      kind,
      activityId,
      detailUrl: template.replace("{activityId}", encodeURIComponent(activityId)),
    };
  }

  MindGraphDocExtract.parseSmartEduUrl = parseSmartEduUrl;
  MindGraphDocExtract.SMARTEDU_DETAIL_TEMPLATES = DETAIL_TEMPLATES;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
