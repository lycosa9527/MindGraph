/**
 * Host registry — merged 435884 + 437609 @match + SmartEdu (~25 sites).
 * @fileoverview One row per host pattern → engine + prep hooks.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /** @typedef {"api-binary"|"canvas-pdf"|"html2canvas-pdf"|"dom-article"} ExtractEngine */

  /**
   * @typedef {object} HostEntry
   * @property {string} id
   * @property {string} label
   * @property {string[]} hosts
   * @property {ExtractEngine} engine
   * @property {string[]} prep
   * @property {string[]} [hideSelectors]
   * @property {string[]} [pageSelectors]
   * @property {string} providerVersion
   */

  /** @type {HostEntry[]} */
  const HOST_ENTRIES = [
    {
      id: "smartedu",
      label: "国家智慧教育",
      hosts: ["basic.smartedu.cn", "smartedu.cn"],
      engine: "api-binary",
      prep: [],
      providerVersion: "tchMaterial-parser",
    },
    {
      id: "wenku",
      label: "百度文库",
      hosts: ["wenku.baidu.com"],
      engine: "canvas-pdf",
      // No expand-all: clicking 展开全文 opens Baidu VIP paywall; capture loaded preview + scroll only.
      prep: ["unblock-copy", "hide-chrome", "autoscroll"],
      autoscrollStepMs: 350,
      autoscrollMaxSteps: 18,
      hideSelectors: [".header-wrapper", ".toolbar-wrap", ".reader-tools"],
      providerVersion: "437609",
    },
    {
      id: "doc88",
      label: "道客巴巴",
      hosts: ["doc88.com"],
      engine: "canvas-pdf",
      prep: ["hide-chrome", "autoscroll"],
      hideSelectors: [".toolbar", ".doc-toolbar", ".page-banner"],
      providerVersion: "437609",
    },
    {
      id: "docin",
      label: "豆丁网",
      hosts: ["docin.com", "jz.docin.com"],
      engine: "canvas-pdf",
      prep: ["hide-chrome", "expand-all", "autoscroll"],
      hideSelectors: [".toolbar", ".docin_header", ".page_bar"],
      providerVersion: "437609",
    },
    {
      id: "taodocs",
      label: "淘豆网",
      hosts: ["taodocs.com", "file.taodocs.com"],
      engine: "canvas-pdf",
      prep: ["autoscroll"],
      providerVersion: "437609",
    },
    {
      id: "book118",
      label: "原创力文档",
      hosts: ["max.book118.com", "book118.com"],
      engine: "canvas-pdf",
      prep: ["hide-chrome", "autoscroll"],
      hideSelectors: [".toolbar", ".header", ".doc-header"],
      providerVersion: "437609",
    },
    {
      id: "cnki",
      label: "中国知网",
      hosts: ["cnki.net"],
      engine: "api-binary",
      prep: ["hide-chrome"],
      hideSelectors: [
        ".reader-toolbar",
        ".toolbar",
        ".topbar",
        ".header-wrap",
        ".cnki-header",
        ".operate-btn",
      ],
      readerMaxPages: 120,
      providerVersion: "CNKI-PDF-RIS-Helper",
    },
    {
      id: "360doc",
      label: "360个人图书馆",
      hosts: ["360doc.com"],
      engine: "dom-article",
      prep: ["unblock-copy"],
      pageSelectors: ["#articlecontent", ".article-content", "article"],
      providerVersion: "435884",
    },
    {
      id: "deliwenku",
      label: "得力文库",
      hosts: ["deliwenku.com"],
      engine: "html2canvas-pdf",
      prep: ["hide-chrome", "autoscroll"],
      pageSelectors: [".page-container", ".reader-page", ".page"],
      providerVersion: "435884",
    },
    {
      id: "mbalib",
      label: "MBA智库",
      hosts: ["doc.mbalib.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".doc-content", ".page"],
      providerVersion: "435884",
    },
    {
      id: "iask",
      label: "爱问文档",
      hosts: ["ishare.iask.com", "iask.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".doc-page", ".page"],
      providerVersion: "435884",
    },
    {
      id: "dugen",
      label: "读根网",
      hosts: ["dugen.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page", ".doc-page"],
      providerVersion: "435884",
    },
    {
      id: "gb688",
      label: "国标网",
      hosts: ["gb688.cn"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page", ".viewer-page"],
      providerVersion: "435884",
    },
    {
      id: "safewk",
      label: "安全文库网",
      hosts: ["safewk.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "renrendoc",
      label: "人人文库",
      hosts: ["renrendoc.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page", ".reader-page"],
      providerVersion: "435884",
    },
    {
      id: "yunzhan365",
      label: "云展网",
      hosts: ["yunzhan365.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page", ".page-container"],
      providerVersion: "435884",
    },
    {
      id: "wenku_so",
      label: "360文库",
      hosts: ["wenku.so.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "wenkub",
      label: "文库吧",
      hosts: ["wenkub.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "jinchutou",
      label: "金锄头",
      hosts: ["jinchutou.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "nrsis",
      label: "自然资源标准",
      hosts: ["nrsis.org.cn"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "ssap",
      label: "中国社会科学文库",
      hosts: ["ssap.com.cn"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "jg_class",
      label: "技工教育网",
      hosts: ["jg.class.com.cn"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "sdlib",
      label: "山东图书馆",
      hosts: ["sdlib.com"],
      engine: "html2canvas-pdf",
      prep: ["autoscroll"],
      pageSelectors: [".page"],
      providerVersion: "435884",
    },
    {
      id: "collab_docs",
      label: "协作文档",
      hosts: ["docs.qq.com", "yuque.com", "feishu.cn", "larksuite.com"],
      engine: "dom-article",
      prep: ["unblock-copy"],
      pageSelectors: ["article", "main", "[role='document']"],
      providerVersion: "Lift_Copy_Restrictions",
    },
    {
      id: "article",
      label: "文章页",
      hosts: [
        "zhihu.com",
        "jianshu.com",
        "csdn.net",
        "cnblogs.com",
        "juejin.cn",
        "segmentfault.com",
      ],
      engine: "dom-article",
      prep: ["unblock-copy"],
      pageSelectors: ['[itemprop="articleBody"]', '[role="article"]', "article", "main"],
      providerVersion: "article-extractor",
    },
  ];

  /** @type {HostEntry} */
  const GENERIC_HOST = {
    id: "generic",
    label: "网页",
    hosts: [],
    engine: "dom-article",
    prep: ["unblock-copy"],
    pageSelectors: ['[itemprop="articleBody"]', '[role="article"]', "article", "main", "body"],
    providerVersion: "mindgraph-capture",
  };

  /**
   * @param {string} hostname
   * @param {string} hostPattern
   * @returns {boolean}
   */
  function hostnameMatchesHostPattern(hostname, hostPattern) {
    const name = (hostname || "").toLowerCase();
    const pattern = (hostPattern || "").toLowerCase();
    if (!name || !pattern) {
      return false;
    }
    return name === pattern || name.endsWith(`.${pattern}`);
  }

  /**
   * @param {string} pageUrl
   * @returns {HostEntry}
   */
  function matchHost(pageUrl) {
    if (!pageUrl || typeof pageUrl !== "string") {
      return GENERIC_HOST;
    }
    let hostname = "";
    try {
      hostname = new URL(pageUrl).hostname.toLowerCase();
    } catch {
      return GENERIC_HOST;
    }
    for (const entry of HOST_ENTRIES) {
      for (const host of entry.hosts) {
        if (hostnameMatchesHostPattern(hostname, host)) {
          return entry;
        }
      }
    }
    return GENERIC_HOST;
  }

  /**
   * @param {string} pageUrl
   * @returns {boolean}
   */
  function isExtractSupportedUrl(pageUrl) {
    const entry = matchHost(pageUrl);
    return entry.id !== "generic" || /^https?:\/\//i.test(pageUrl || "");
  }

  MindGraphDocExtract.HOST_ENTRIES = HOST_ENTRIES;
  MindGraphDocExtract.GENERIC_HOST = GENERIC_HOST;
  MindGraphDocExtract.hostnameMatchesHostPattern = hostnameMatchesHostPattern;
  MindGraphDocExtract.matchHost = matchHost;
  MindGraphDocExtract.isExtractSupportedUrl = isExtractSupportedUrl;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
