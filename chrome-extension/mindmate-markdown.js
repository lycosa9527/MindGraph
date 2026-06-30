/**
 * Safe subset markdown → HTML for MindMate assistant bubbles (no raw HTML passthrough).
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};

  /**
   * @param {string} text
   * @returns {string}
   */
  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * @param {string} href
   * @returns {boolean}
   */
  function isSafeLinkHref(href) {
    const raw = (href || "").trim();
    if (!raw) {
      return false;
    }
    try {
      const url = new URL(raw, "https://example.invalid");
      return url.protocol === "http:" || url.protocol === "https:" || url.protocol === "mailto:";
    } catch {
      return false;
    }
  }

  /**
   * @param {string} text
   * @returns {string}
   */
  function renderInlineMarkdown(text) {
    let out = escapeHtml(text);
    const codeSlots = [];
    out = out.replace(/`([^`\n]+)`/g, (_match, code) => {
      const key = `__MM_CODE_${codeSlots.length}__`;
      codeSlots.push(`<code>${code}</code>`);
      return key;
    });
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, href) => {
      if (!isSafeLinkHref(href)) {
        return match;
      }
      const safeHref = escapeHtml(href.trim());
      return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });
    out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
    out = out.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    out = out.replace(/_([^_\n]+)_/g, "<em>$1</em>");
    for (let i = 0; i < codeSlots.length; i += 1) {
      out = out.replace(`__MM_CODE_${i}__`, codeSlots[i]);
    }
    return out;
  }

  /**
   * @param {string[]} lines
   * @returns {string[]}
   */
  function renderListBlock(lines) {
    const ordered = /^\d+\.\s+/.test(lines[0]);
    const tag = ordered ? "ol" : "ul";
    const items = lines.map((line) => {
      const item = ordered ? line.replace(/^\d+\.\s+/, "") : line.replace(/^[-*+]\s+/, "");
      return `<li>${renderInlineMarkdown(item)}</li>`;
    });
    return [`<${tag}>${items.join("")}</${tag}>`];
  }

  /**
   * @param {string} block
   * @returns {string}
   */
  function renderMarkdownBlock(block) {
    const trimmed = block.trim();
    if (!trimmed) {
      return "";
    }
    const hrMatch = trimmed.match(/^(-{3,}|\*{3,}|_{3,})$/);
    if (hrMatch) {
      return "<hr>";
    }
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      return `<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`;
    }
    const lines = trimmed.split("\n");
    const listLine = /^(\d+\.\s+|[-*+]\s+)/;
    if (lines.every((line) => listLine.test(line.trim()))) {
      return renderListBlock(lines.map((line) => line.trim())).join("");
    }
    if (lines.every((line) => line.startsWith("> ") || line === ">")) {
      const quote = lines.map((line) => line.replace(/^>\s?/, "")).join("\n");
      return `<blockquote>${renderMarkdownBlock(quote)}</blockquote>`;
    }
    const parts = trimmed.split(/\n{2,}/).map((part) => {
      const inline = part.split("\n").map((line) => renderInlineMarkdown(line)).join("<br>");
      return `<p>${inline}</p>`;
    });
    return parts.join("");
  }

  /**
   * @param {string} markdown
   * @returns {string}
   */
  function renderMarkdownToHtml(markdown) {
    const source = String(markdown || "");
    if (!source.trim()) {
      return "";
    }
    const parts = [];
    const fence = /```(\w*)\n?([\s\S]*?)```/g;
    let lastIndex = 0;
    let match = fence.exec(source);
    while (match) {
      if (match.index > lastIndex) {
        parts.push({ type: "text", value: source.slice(lastIndex, match.index) });
      }
      parts.push({ type: "code", lang: match[1] || "", value: match[2] || "" });
      lastIndex = match.index + match[0].length;
      match = fence.exec(source);
    }
    if (lastIndex < source.length) {
      parts.push({ type: "text", value: source.slice(lastIndex) });
    }
    if (parts.length === 0) {
      parts.push({ type: "text", value: source });
    }

    const html = [];
    for (const part of parts) {
      if (part.type === "code") {
        const langClass = part.lang ? ` class="language-${escapeHtml(part.lang)}"` : "";
        html.push(`<pre><code${langClass}>${escapeHtml(part.value.replace(/\n$/, ""))}</code></pre>`);
        continue;
      }
      const blocks = part.value.replace(/\r\n/g, "\n").split(/\n{2,}/);
      for (const block of blocks) {
        const rendered = renderMarkdownBlock(block);
        if (rendered) {
          html.push(rendered);
        }
      }
    }
    return `<div class="mindmate-md">${html.join("")}</div>`;
  }

  /**
   * @param {HTMLElement} bubble
   * @param {string} text
   * @param {"user" | "assistant"} role
   */
  function applyMessageBubbleContent(bubble, text, role) {
    if (!bubble) {
      return;
    }
    if (role === "assistant" && text.trim()) {
      try {
        bubble.classList.add("mindmate-msg-bubble-md");
        bubble.innerHTML = renderMarkdownToHtml(text);
        return;
      } catch {
        bubble.classList.remove("mindmate-msg-bubble-md");
        bubble.textContent = text;
        return;
      }
    }
    bubble.classList.remove("mindmate-msg-bubble-md");
    bubble.textContent = text;
  }

  MindGraphMindMate.escapeHtml = escapeHtml;
  MindGraphMindMate.isSafeLinkHref = isSafeLinkHref;
  MindGraphMindMate.renderInlineMarkdown = renderInlineMarkdown;
  MindGraphMindMate.renderMarkdownToHtml = renderMarkdownToHtml;
  MindGraphMindMate.applyMessageBubbleContent = applyMessageBubbleContent;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
