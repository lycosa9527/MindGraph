/**
 * Markdown rendering composable.
 *
 * Uses markdown-it (already installed) + DOMPurify for XSS-safe HTML
 * and highlight.js for fenced-code syntax highlighting.
 *
 * Uses highlight.js/lib/common for a curated set of popular languages
 * (bash, css, js, json, python, sql, ts, xml, etc.) to keep bundle size small.
 */
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import MarkdownIt from 'markdown-it'

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

export function useMarkdown() {
  function render(content: string): string {
    const raw = md.render(content)
    return DOMPurify.sanitize(raw, {
      ADD_TAGS: ['pre', 'code'],
      ADD_ATTR: ['class'],
    })
  }

  return { render }
}
