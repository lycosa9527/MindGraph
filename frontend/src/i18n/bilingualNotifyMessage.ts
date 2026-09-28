/**
 * Toast / notification copy: primary locale, optional presenter line below.
 * Message keys only — never pass model output or API detail strings.
 */
import { type VNode, h } from 'vue'

import { resolveBilingual } from '@/i18n/resolveBilingual'

export function bilingualNotifyMessage(
  key: string,
  params?: Record<string, unknown>
): string | VNode {
  const copy = resolveBilingual(key, params)
  if (!copy.secondary) {
    return copy.primary
  }
  return h('span', { class: 'i18n-toast' }, [
    h('span', { class: 'i18n-toast__primary' }, copy.primary),
    h('span', { class: 'i18n-toast__secondary' }, copy.secondary),
  ])
}

/** Same untranslated suffix on both lines (counts, filenames). */
export function bilingualNotifyWithSuffix(
  key: string,
  suffix: string,
  params?: Record<string, unknown>
): string | VNode {
  const copy = resolveBilingual(key, params)
  const primary = `${copy.primary}${suffix}`
  if (!copy.secondary) {
    return primary
  }
  return h('span', { class: 'i18n-toast' }, [
    h('span', { class: 'i18n-toast__primary' }, primary),
    h('span', { class: 'i18n-toast__secondary' }, `${copy.secondary}${suffix}`),
  ])
}

/** One toast made of several catalog messages (mention errors). */
export function joinNotifyMessages(
  parts: Array<string | VNode>,
  separator = ' · '
): string | VNode {
  if (parts.length === 0) {
    return ''
  }
  if (parts.every((part) => typeof part === 'string')) {
    return parts.join(separator)
  }
  return h('div', { class: 'i18n-toast-stack' }, parts)
}
