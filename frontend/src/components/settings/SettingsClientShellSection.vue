<script setup lang="ts">
/**
 * Account-tab control that locks this browser to the mobile or desktop shell.
 */
import { computed, shallowRef } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { commitClientShell } from '@/stores/clientShellState'
import { useUIStore } from '@/stores/ui'
import '@/styles/settings-language-swiss.css'
import { clientShellLock } from '@/utils/clientShellLock'
import type { ClientShell } from '@/utils/clientShellLock'

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const saving = shallowRef(false)

const selection = computed<ClientShell>(() => {
  if (clientShellLock.value) return clientShellLock.value
  return uiStore.isMobile ? 'mobile' : 'desktop'
})

async function choose(shell: ClientShell): Promise<void> {
  if (saving.value || clientShellLock.value === shell) return
  saving.value = true
  const saved = await commitClientShell(shell)
  saving.value = false
  if (!saved) notify.errorKey('auth.clientShellSaveError')
  else notify.successKey('auth.clientShellSaved')
}
</script>

<template>
  <section>
    <div class="language-settings-swiss__kicker">
      <I18nText k="auth.clientShell" />
    </div>
    <div
      class="language-settings-canvas-segmented"
      role="radiogroup"
      :aria-label="t('auth.clientShell')"
    >
      <button
        type="button"
        role="radio"
        class="language-settings-canvas-segment"
        :class="{ 'is-active': selection === 'mobile' }"
        :aria-checked="selection === 'mobile'"
        :disabled="saving"
        @click="choose('mobile')"
      >
        <I18nText k="auth.clientShellMobile" />
      </button>
      <button
        type="button"
        role="radio"
        class="language-settings-canvas-segment"
        :class="{ 'is-active': selection === 'desktop' }"
        :aria-checked="selection === 'desktop'"
        :disabled="saving"
        @click="choose('desktop')"
      >
        <I18nText k="auth.clientShellDesktop" />
      </button>
    </div>
    <p class="language-settings-swiss__hint">
      <I18nText k="auth.clientShellHint" />
    </p>
  </section>
</template>
