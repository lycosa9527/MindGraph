/**
 * Remove model thinking blocks from MindMate text when the organization switch is off.
 * Tag names match the DingTalk reply filter.
 */

const THINK_BLOCK =
  /<(?:think|thinking|redacted_thinking|reasoning)\b[^>]*>[\s\S]*?<\/\s*(?:think|thinking|redacted_thinking|reasoning)\s*>/gi

const BACKTICK_THINK = /`<think>`[\s\S]*?`<\/think>`/gi

export function stripMindmateThinkingBlocks(content: string): string {
  let text = content.replace(/\uFF1C/g, '<').replace(/\uFF1E/g, '>')
  let previous = ''
  while (text !== previous) {
    previous = text
    text = text.replace(BACKTICK_THINK, '').replace(THINK_BLOCK, '')
  }
  return text.trim()
}
