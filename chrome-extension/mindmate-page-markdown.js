/**
 * Injected into the active tab — article-root DOM to markdown for MindMate context.
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

  /**
   * @returns {Element}
   */
  function findArticleRoot() {
    const selectors = [
      '[itemprop="articleBody"]',
      '[role="article"]',
      "article",
      "main",
      "[role='main']",
      "#articlecontent",
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
   * @param {number} maxChars
   * @returns {{ title: string, url: string, markdown: string, fromSelection: boolean }}
   */
  function extractPageMarkdown(maxChars) {
    const title = document.title || "";
    const url = window.location.href || "";
    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      return {
        title,
        url,
        markdown: truncateMarkdown(selection.toString().trim(), maxChars),
        fromSelection: true,
      };
    }
    const root = findArticleRoot();
    const markdown = truncateMarkdown(domToMarkdown(root), maxChars);
    return {
      title,
      url,
      markdown,
      fromSelection: false,
    };
  }

  global.__MGMindMatePageMarkdown = {
    extractPageMarkdown,
    domToMarkdown,
    truncateMarkdown,
    findArticleRoot,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
