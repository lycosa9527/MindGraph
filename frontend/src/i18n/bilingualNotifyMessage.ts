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
