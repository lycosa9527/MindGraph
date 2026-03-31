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

/**
 * Sanitize HTML from markdown-it before assigning to v-html.
 * Use for any user- or model-generated markdown; linkify and future plugins must not bypass XSS controls.
 */
export function sanitizeMarkdownItHtml(html: string): string {
  if (!html) {
    return ''
  }
  return DOMPurify.sanitize(html, markdownKatexDomPurifyConfig)
}
