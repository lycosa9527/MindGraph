/**
 * Markdown-it + KaTeX renderer (loaded on demand via lazyMarkdown.ts).
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
import { markdownKatexDomPurifyConfig, installMarkdownLinkSanitizeHook } from '@/composables/core/markdownKatexSanitize'

type MarkdownItInstance = InstanceType<typeof MarkdownIt>

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

export function renderRichMarkdownHtmlImpl(content: string): string {
  const prepared = normalizeKatexDelimitersForMarkdownIt(
    replaceMathLivePlaceholdersForKatex(content)
  )
  const raw = md.render(prepared)
  installMarkdownLinkSanitizeHook()
  return DOMPurify.sanitize(raw, markdownKatexDomPurifyConfig)
}
