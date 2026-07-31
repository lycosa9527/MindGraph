/**
 * Maite toast bridge — maps maite:error bus events to notify.*.
 */
import { onScopeDispose } from 'vue'

import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'

const WARNING_CODES = new Set(['variants_incomplete', 'variant_answer_required'])

function looksLikeErrorCode(message: string): boolean {
  return /^[a-z][a-z0-9_]*$/.test(message)
}

export function useMaiteNotifications(): void {
  const { t } = useLanguage()

  function resolveMessage(message: string): string {
    const trimmed = message.trim()
    if (!trimmed) {
      return t('maite.errors.generic')
    }
    if (looksLikeErrorCode(trimmed)) {
      const key = `maite.errors.${trimmed}`
      const translated = t(key)
      if (translated !== key) {
        return translated
      }
      return t('maite.errors.generic')
    }
    return trimmed
  }

  const offError = eventBus.on('maite:error', ({ message }) => {
    const text = resolveMessage(message)
    if (WARNING_CODES.has(message)) {
      notify.warning(text)
      return
    }
    notify.error(text)
  })

  onScopeDispose(() => {
    offError()
  })
}
