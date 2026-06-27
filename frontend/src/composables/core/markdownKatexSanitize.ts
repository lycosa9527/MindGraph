/**
 * DOMPurify options for markdown-it output that includes KaTeX HTML (spans, SVG)
 * plus standard CommonMark elements (headings, lists, links, code).
 */
import DOMPurify from 'dompurify'

/** Tags produced by markdown-it + highlight.js + @vscode/markdown-it-katex (KaTeX HTML). */
const MARKDOWN_KATEX_TAGS = [
  'a',
  'annotation',
  'b',
  'blockquote',
  'br',
  'code',
  'del',
  'defs',
  'div',
  'em',
  'g',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'i',
  'img',
  'li',
  'line',
  'math',
  'menclose',
  'mfenced',
  'mfrac',
  'mglyph',
  'mi',
  'mlabeledtr',
  'mmultiscripts',
  'mn',
  'mo',
  'mover',
  'mpadded',
  'mphantom',
  'mroot',
  'mrow',
  'ms',
  'mspace',
  'msqrt',
  'mstyle',
  'msub',
  'msubsup',
  'msup',
  'mtable',
  'mtd',
  'mtext',
  'mtr',
  'munder',
  'munderover',
  'ol',
  'p',
  'path',
  'pre',
  'rect',
  's',
  'semantics',
  'span',
  'strike',
  'strong',
  'sub',
  'sup',
  'svg',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'u',
  'ul',
  'use',
] as const

/** Attributes used by KaTeX, SVG, markdown links, and code blocks. */
const MARKDOWN_KATEX_ATTR = [
  'alt',
  'aria-hidden',
  'aria-label',
  'class',
  'clip-path',
  'd',
  'fill',
  'focusable',
  'height',
  'href',
  'id',
  'marker-end',
  'marker-start',
  'preserveAspectRatio',
  'rel',
  'role',
  'src',
  'stroke',
  'stroke-linecap',
  'stroke-linejoin',
  'stroke-width',
  'style',
  'target',
  'title',
  'viewBox',
  'width',
  'xmlns',
  'x',
  'x1',
  'x2',
  'y',
  'y1',
  'y2',
] as const

export const markdownKatexDomPurifyConfig: { ADD_TAGS: string[]; ADD_ATTR: string[] } = {
  ADD_TAGS: [...MARKDOWN_KATEX_TAGS],
  ADD_ATTR: [...MARKDOWN_KATEX_ATTR],
}

let markdownLinkSanitizeHookInstalled = false

/** Install once; safe to call from every sanitize entry point. */
export function installMarkdownLinkSanitizeHook(): void {
  if (markdownLinkSanitizeHookInstalled) {
    return
  }
  markdownLinkSanitizeHookInstalled = true
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName !== 'A') {
      return
    }
    const href = node.getAttribute('href')
    if (!href) {
      return
    }
    const lowered = href.trim().toLowerCase()
    if (lowered.startsWith('javascript:') || lowered.startsWith('data:')) {
      node.removeAttribute('href')
      return
    }
    node.setAttribute('rel', 'noopener noreferrer')
    if (lowered.startsWith('http://') || lowered.startsWith('https://')) {
      node.setAttribute('target', '_blank')
    }
  })
}

/**
 * Sanitize HTML from markdown-it before assigning to v-html.
 * Prefer `renderRichMarkdownHtml` from `@/composables/core/useMarkdown` so math and fenced code run
 * through the markdown pipeline before sanitization. Use this when HTML was produced elsewhere.
 */
export function sanitizeMarkdownItHtml(html: string): string {
  if (!html) {
    return ''
  }
  installMarkdownLinkSanitizeHook()
  return DOMPurify.sanitize(html, markdownKatexDomPurifyConfig)
}
