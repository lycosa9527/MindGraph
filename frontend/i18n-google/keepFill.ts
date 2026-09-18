/**
 * Values that stay English when gap-filling a picker locale from zh.
 */
export const KEEP_VALUES = new Set([
  'Mind Platform',
  'MindGraph',
  'MindMate',
  'MindBot',
  'TEST',
  'www.mindspringedu.com',
])

const BARE_KEY_COMBO = /^(Ctrl|Shift|Alt|⌘)\+[A-Za-z0-9]+$/i
const BARE_VERSION = /^V\d+$/i
export const PLACEHOLDER_RE = /\{[^}]+\}/g

export function isKeepFill(value: string): boolean {
  const v = value.trim()
  if (v.length === 0) {
    return true
  }
  if (KEEP_VALUES.has(v)) {
    return true
  }
  const withoutSlots = v.replace(PLACEHOLDER_RE, '').trim()
  if (withoutSlots.length === 0 || !/\p{L}/u.test(withoutSlots)) {
    return true
  }
  if (!/\p{L}/u.test(v)) {
    return true
  }
  return BARE_KEY_COMBO.test(v) || BARE_VERSION.test(v)
}
