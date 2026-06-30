/**
 * Injected into the active tab — article / PDF.js reader DOM to markdown for MindMate.
 */
(function (global) {
  "use strict";

  const SKIP_TAGS = new Set([
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "object",
    "nav",
    "footer",
    "header",
    "aside",
  ]);

  const READER_NEXT_SELECTORS = [
    "#nextPage",
    "#next",
    ".next-page",
    ".page-next",
    ".reader-next",
    'button[title*="下一页"]',
    'a[title*="下一页"]',
    '[aria-label*="下一页"]',
    '[aria-label*="Next"]',
    ".toolbar .next",
    ".reader-toolbar .next",
  ];

  /**
   * @param {number} ms
   * @returns {Promise<void>}
   */
  function sleep(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  /**
   * @returns {boolean}
   */
  function isOnlineReaderPage() {
    const path = (window.location.pathname || "").toLowerCase();
    return path.includes("/reader/") || path.includes("/xmlread/trialread");
  }

  /**
   * @returns {string}
   */
  function readPageTitle() {
    const selectors = [".brief h1", ".reader-title", ".doc-title", "h1.title", "h1"];
    for (const sel of selectors) {
      try {
        const node = document.querySelector(sel);
        if (node && node.textContent && node.textContent.trim()) {
          return node.textContent.trim().replace(/\s*网络首发\s*$/, "");
        }
      } catch {
        /* ignore */
      }
    }
    return (document.title || "").replace(/\s*-\s*中国知网.*$/i, "").trim();
  }

  /**
   * @returns {Element}
   */
  function findArticleRoot() {
    if (isOnlineReaderPage()) {
      const readerSelectors = [
        "#viewerContainer",
        "#viewer",
        ".reader-container",
        ".reader-main",
        ".reader-content",
        ".pdf-viewer",
      ];
      for (const sel of readerSelectors) {
        try {
          const node = document.querySelector(sel);
          if (node) {
            return node;
          }
        } catch {
          /* ignore */
        }
      }
    }

    const selectors = [
      '[itemprop="articleBody"]',
      '[role="article"]',
      "article",
      "main",
      "[role='main']",
      "#articlecontent",
      ".wx-content",
      "#ChDivSummary",
      ".brief",
      ".reader-container",
    ];
    for (const sel of selectors) {
      try {
        const node = document.querySelector(sel);
        if (node) {
          return node;
        }
      } catch {
        /* ignore invalid selector */
      }
    }
    return document.body;
  }

  /**
   * @param {string[]} selectors
   * @returns {HTMLElement | null}
   */
  function findNextPageControl(selectors) {
    for (const sel of selectors) {
      let nodes = [];
      try {
        nodes = Array.from(document.querySelectorAll(sel));
      } catch {
        nodes = [];
      }
      for (const node of nodes) {
        if (!(node instanceof HTMLElement)) {
          continue;
        }
        if (node.matches(":disabled") || node.getAttribute("aria-disabled") === "true") {
          continue;
        }
        if (node.offsetParent === null && node.tagName !== "BODY") {
          continue;
        }
        return node;
      }
    }
    return null;
  }

  /**
   * @param {Element} [root]
   * @returns {string}
   */
  function extractPdfJsTextLayerMarkdown(root) {
    const scope = root || document;
    const spans = scope.querySelectorAll(
      '.textLayer span[role="presentation"], .textLayer span, [class*="textLayer"] span',
    );
    if (!spans.length) {
      return "";
    }

    /** @type {Array<{ top: number, left: number, text: string }>} */
    const items = [];
    spans.forEach((span) => {
      const text = (span.textContent || "").replace(/\s+/g, " ").trim();
      if (!text) {
        return;
      }
      const rect = span.getBoundingClientRect();
      items.push({
        top: Math.round(rect.top),
        left: Math.round(rect.left),
        text,
      });
    });
    if (!items.length) {
      return "";
    }

    items.sort((a, b) => (a.top === b.top ? a.left - b.left : a.top - b.top));

    const lines = [];
    let currentTop = items[0].top;
    let lineParts = [];
    const lineThreshold = 4;

    items.forEach((item) => {
      if (Math.abs(item.top - currentTop) > lineThreshold) {
        if (lineParts.length) {
          lines.push(lineParts.join(" ").trim());
        }
        lineParts = [item.text];
        currentTop = item.top;
        return;
      }
      lineParts.push(item.text);
    });
    if (lineParts.length) {
      lines.push(lineParts.join(" ").trim());
    }

    return lines.filter(Boolean).join("\n\n").trim();
  }

  /**
   * @param {Element} root
   * @returns {string}
   */
  function extractPlainTextMarkdown(root) {
    if (!root) {
      return "";
    }
    return (root.innerText || "")
      .replace(/\r\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]+\n/g, "\n")
      .trim();
  }

  /**
   * @param {Element} el
   * @returns {boolean}
   */
  function shouldSkip(el) {
    if (!(el instanceof Element)) {
      return true;
    }
    const tag = el.tagName.toLowerCase();
    if (SKIP_TAGS.has(tag)) {
      return true;
    }
    if (el.getAttribute("aria-hidden") === "true") {
      return true;
    }
    if (el.classList && (el.classList.contains("textLayer") || el.classList.contains("toolbar"))) {
      return true;
    }
    return false;
  }

  /**
   * @param {Element} el
   * @returns {string}
   */
  function inlineMarkdown(el) {
    let out = "";
    el.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        out += node.textContent || "";
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE || shouldSkip(node)) {
        return;
      }
      const tag = node.tagName.toLowerCase();
      const inner = inlineMarkdown(node).replace(/\s+/g, " ").trim();
      if (!inner) {
        return;
      }
      if (tag === "strong" || tag === "b") {
        out += `**${inner}**`;
      } else if (tag === "em" || tag === "i") {
        out += `*${inner}*`;
      } else if (tag === "code") {
        out += `\`${inner}\``;
      } else if (tag === "a") {
        const href = node.getAttribute("href") || "";
        out += href ? `[${inner}](${href})` : inner;
      } else if (tag === "br") {
        out += "\n";
      } else {
        out += inner;
      }
    });
    return out.replace(/\s+/g, " ").trim();
  }

  /**
   * @param {Element} el
   * @param {number} listDepth
   * @returns {string[]}
   */
  function blockLines(el, listDepth) {
    if (shouldSkip(el)) {
      return [];
    }
    const tag = el.tagName.toLowerCase();
    const lines = [];

    if (/^h[1-6]$/.test(tag)) {
      const level = parseInt(tag.slice(1), 10);
      const text = inlineMarkdown(el);
      if (text) {
        lines.push(`${"#".repeat(level)} ${text}`);
      }
      return lines;
    }

    if (tag === "p") {
      const text = inlineMarkdown(el);
      if (text) {
        lines.push(text);
      }
      return lines;
    }

    if (tag === "blockquote") {
      const inner = childrenMarkdown(el, listDepth)
        .split("\n")
        .filter(Boolean)
        .map((line) => `> ${line}`)
        .join("\n");
      if (inner) {
        lines.push(inner);
      }
      return lines;
    }

    if (tag === "pre") {
      const text = (el.textContent || "").trim();
      if (text) {
        lines.push("```\n" + text + "\n```");
      }
      return lines;
    }

    if (tag === "ul" || tag === "ol") {
      let index = 0;
      el.querySelectorAll(":scope > li").forEach((li) => {
        const prefix = tag === "ol" ? `${index + 1}. ` : "- ";
        const body = childrenMarkdown(li, listDepth + 1).replace(/\n/g, "\n  ");
        if (body) {
          lines.push(`${"  ".repeat(listDepth)}${prefix}${body}`);
          index += 1;
        }
      });
      return lines;
    }

    if (tag === "li") {
      return [childrenMarkdown(el, listDepth)];
    }

    return [childrenMarkdown(el, listDepth)];
  }

  /**
   * @param {Element} el
   * @param {number} listDepth
   * @returns {string}
   */
  function childrenMarkdown(el, listDepth) {
    const chunks = [];
    el.childNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = (node.textContent || "").replace(/\s+/g, " ").trim();
        if (text) {
          chunks.push(text);
        }
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return;
      }
      const tag = node.tagName.toLowerCase();
      if (SKIP_TAGS.has(tag)) {
        return;
      }
      if (tag === "ul" || tag === "ol" || tag === "p" || /^h[1-6]$/.test(tag) || tag === "pre" || tag === "blockquote") {
        chunks.push(blockLines(node, listDepth).join("\n"));
      } else {
        const inline = inlineMarkdown(node);
        if (inline) {
          chunks.push(inline);
        }
      }
    });
    return chunks.filter(Boolean).join("\n\n").trim();
  }

  /**
   * @param {Element} root
   * @returns {string}
   */
  function domToMarkdown(root) {
    if (!root) {
      return "";
    }
    const lines = blockLines(root, 0);
    return lines.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
  }

  /**
   * @param {string} text
   * @param {number} maxChars
   * @returns {string}
   */
  function truncateMarkdown(text, maxChars) {
    if (!text || text.length <= maxChars) {
      return text || "";
    }
    return `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
  }

  /**
   * @param {Element} root
   * @param {number} maxPages
   * @returns {Promise<string>}
   */
  async function extractReaderTextWithPaging(root, maxPages) {
    const limit = typeof maxPages === "number" && maxPages > 0 ? maxPages : 80;
    const seen = new Set();
    const parts = [];

    const pushUnique = (chunk) => {
      const text = (chunk || "").trim();
      if (!text || seen.has(text)) {
        return;
      }
      seen.add(text);
      parts.push(text);
    };

    for (let step = 0; step < limit; step += 1) {
      pushUnique(extractPdfJsTextLayerMarkdown(root));
      if (!isOnlineReaderPage()) {
        break;
      }
      const next = findNextPageControl(READER_NEXT_SELECTORS);
      if (!next) {
        break;
      }
      const before = parts.length;
      next.click();
      await sleep(500);
      pushUnique(extractPdfJsTextLayerMarkdown(root));
      if (parts.length === before) {
        break;
      }
    }

    return parts.join("\n\n").trim();
  }

  /**
   * @param {number} maxChars
   * @returns {Promise<{ title: string, url: string, markdown: string, fromSelection: boolean, source?: string }>}
   */
  async function extractPageMarkdownAsync(maxChars) {
    const title = readPageTitle();
    const url = window.location.href || "";
    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      return {
        title,
        url,
        markdown: truncateMarkdown(selection.toString().trim(), maxChars),
        fromSelection: true,
        source: "selection",
      };
    }

    const root = findArticleRoot();

    let markdown = extractPdfJsTextLayerMarkdown(root);
    let source = "pdf-text-layer";
    if (isOnlineReaderPage() && markdown.length < 120) {
      markdown = await extractReaderTextWithPaging(root, 80);
      source = "pdf-text-layer-paged";
    }

    if (!markdown || markdown.length < 80) {
      const domMd = domToMarkdown(root);
      if (domMd.length > (markdown || "").length) {
        markdown = domMd;
        source = "dom-markdown";
      }
    }

    if (!markdown || markdown.length < 40) {
      const plain = extractPlainTextMarkdown(root);
      if (plain.length > (markdown || "").length) {
        markdown = plain;
        source = "plain-text";
      }
    }

    return {
      title,
      url,
      markdown: truncateMarkdown(markdown, maxChars),
      fromSelection: false,
      source,
    };
  }

  /**
   * @param {number} maxChars
   * @returns {{ title: string, url: string, markdown: string, fromSelection: boolean }}
   */
  function extractPageMarkdown(maxChars) {
    const root = findArticleRoot();
    const selection = window.getSelection();
    const title = readPageTitle();
    const url = window.location.href || "";
    if (selection && selection.toString().trim()) {
      return {
        title,
        url,
        markdown: truncateMarkdown(selection.toString().trim(), maxChars),
        fromSelection: true,
      };
    }
    let markdown = extractPdfJsTextLayerMarkdown(root);
    if (!markdown) {
      markdown = domToMarkdown(root);
    }
    if (!markdown) {
      markdown = extractPlainTextMarkdown(root);
    }
    return {
      title,
      url,
      markdown: truncateMarkdown(markdown, maxChars),
      fromSelection: false,
    };
  }

  global.__MGMindMatePageMarkdown = {
    extractPageMarkdown,
    extractPageMarkdownAsync,
    domToMarkdown,
    truncateMarkdown,
    findArticleRoot,
    extractPdfJsTextLayerMarkdown,
    extractPlainTextMarkdown,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
