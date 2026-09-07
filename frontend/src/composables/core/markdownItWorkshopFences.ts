/**
 * Zulip fence aliases used by the 研习社 compose toolbar: ```quote and ```spoiler.
 */
import type MarkdownIt from 'markdown-it'

type MarkdownItInstance = InstanceType<typeof MarkdownIt>

export function markdownItWorkshopFences(md: MarkdownItInstance): void {
  const defaultFence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, idx, options, env, slf) => {
    const token = tokens[idx]
    const info = (token.info || '').trim()
    const space = info.search(/\s/)
    const lang = (space === -1 ? info : info.slice(0, space)).toLowerCase()
    if (lang === 'quote') {
      const inner = md.render(token.content)
      return `<blockquote class="workshop-quote">${inner}</blockquote>\n`
    }
    if (lang === 'spoiler') {
      const header = (space === -1 ? '' : info.slice(space).trim()) || '…'
      const inner = md.render(token.content)
      return (
        `<details class="workshop-spoiler"><summary>${md.utils.escapeHtml(header)}</summary>` +
        `${inner}</details>\n`
      )
    }
    if (defaultFence) {
      return defaultFence(tokens, idx, options, env, slf)
    }
    return slf.renderToken(tokens, idx, options)
  }
}
