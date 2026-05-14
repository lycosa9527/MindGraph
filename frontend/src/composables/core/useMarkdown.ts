/**
 * Markdown rendering composable.
 *
 * Uses markdown-it + @vscode/markdown-it-katex + KaTeX for math, DOMPurify for XSS-safe HTML.
 * `katex` is passed into the plugin so it is the same instance extended by `katex/contrib/mhchem` (`\\ce`).
 * and highlight.js for fenced-code syntax highlighting.
 *
 * Uses highlight.js/lib/common for a curated set of popular languages
 * (bash, css, js, json, python, sql, ts, xml, etc.) to keep bundle size small.
 */
import markdownItKatexImport from '@vscode/markdown-it-katex'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/common'
import katex from 'katex'
import 'katex/contrib/mhchem'
import MarkdownIt from 'markdown-it'

import {
  normalizeKatexDelimitersForMarkdownIt,
  replaceMathLivePlaceholdersForKatex,
} from '@/composables/core/markdownKatexDelimiter'
import { markdownKatexDomPurifyConfig } from '@/composables/core/markdownKatexSanitize'

type MarkdownItInstance = InstanceType<typeof MarkdownIt>

/** CJS/ESM interop: Vite may expose the plugin as `{ default: fn }` instead of `fn`. */
function resolveMarkdownItKatexPlugin(): (
  md: MarkdownItInstance,
  options?: { throwOnError?: boolean }
) => MarkdownItInstance {
  const mod = markdownItKatexImport as unknown
  if (typeof mod === 'function') {
    return mod as (
      md: MarkdownItInstance,
      options?: { throwOnError?: boolean }
    ) => MarkdownItInstance
  }
  const inner = (mod as { default?: unknown }).default
  if (typeof inner === 'function') {
    return inner as (
      md: MarkdownItInstance,
      options?: { throwOnError?: boolean }
    ) => MarkdownItInstance
  }
  throw new Error('@vscode/markdown-it-katex: expected a markdown-it plugin function')
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return (
          '<pre class="hljs"><code>' +
          hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
          '</code></pre>'
        )
      } catch {
        /* fall through */
      }
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  },
})

md.use(resolveMarkdownItKatexPlugin(), { throwOnError: false, katex })

/**
 * Markdown → sanitized HTML with KaTeX math, fenced-code highlighting, and DOMPurify allowlists.
 * Use for MindMate bubbles, workshop chat (via {@link useMarkdown}), share/export, debateverse,
 * ask-once, changelog modal, and anywhere model or user prose is rendered to `v-html`.
 */
export function renderRichMarkdownHtml(content: string): string {
  const prepared = normalizeKatexDelimitersForMarkdownIt(
    replaceMathLivePlaceholdersForKatex(content)
  )
  const raw = md.render(prepared)
  return DOMPurify.sanitize(raw, markdownKatexDomPurifyConfig)
}

/**
 * Same as {@link renderRichMarkdownHtml}. Kept for diagram label measurement and lazy pipeline imports.
 */
export function renderMarkdownForDiagramLabelMeasure(content: string): string {
  return renderRichMarkdownHtml(content)
}

export function useMarkdown() {
  function render(content: string): string {
    return renderRichMarkdownHtml(content)
  }

  return { render }
}
