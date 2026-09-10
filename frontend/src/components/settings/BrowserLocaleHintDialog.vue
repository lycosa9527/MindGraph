<script setup lang="ts">
/**
 * First-visit hint when browser is en/az/th but UI is still default Chinese.
 */
import { computed, ref, watch } from 'vue'

import { Languages } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { SUPPORTED_UI_LOCALES, matchedPromptLanguageForUiLocale } from '@/i18n/locales'
import type { Language } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import { persistLanguagePreferencesIfAuthenticated } from '@/utils/persistLanguagePreferences'

const visible = defineModel<boolean>({ required: true })

const uiStore = useUIStore()
const { t } = useLanguage()

const targetLocale = ref<Language>('en')

const targetDisplayName = computed(
  () =>
    SUPPORTED_UI_LOCALES.find((e) => e.code === targetLocale.value)?.nativeName ??
    targetLocale.value
)

watch(visible, (v) => {
  if (v && typeof navigator !== 'undefined') {
    const nav = navigator.language.toLowerCase()
    if (nav.startsWith('az')) {
      targetLocale.value = 'az'
    } else if (nav.startsWith('th')) {
      targetLocale.value = 'th'
    } else {
      targetLocale.value = 'en'
    }
  }
})

function handleSwitch(): void {
  const loc = targetLocale.value
  uiStore.setUiLanguageExplicit(true)
  uiStore.setLanguage(loc)
  if (!uiStore.matchPromptToUi) {
    const matched = matchedPromptLanguageForUiLocale(loc)
    if (matched !== null) {
      uiStore.setPromptLanguage(matched)
    }
  }
  persistLanguagePreferencesIfAuthenticated()
  visible.value = false
}

function handleKeepChinese(): void {
  uiStore.setUiLanguageExplicit(true)
  persistLanguagePreferencesIfAuthenticated()
  visible.value = false
}

function handleDontAsk(): void {
  uiStore.setBrowserLocaleHintDismissed(true)
  visible.value = false
}
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('swissGlass.hero.localeHint.ribbon')"
    :title="t('swissGlass.hero.localeHint.title')"
    :line1="t('swissGlass.hero.localeHint.line1')"
    :icon="Languages"
    width="min(400px, 92vw)"
  >
    <p class="text-stone-700 dark:text-stone-300 text-sm leading-relaxed">
      {{ t('app.browserLocale.body', { name: targetDisplayName }) }}
    </p>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="handleDontAsk"
        >
          {{ t('app.browserLocale.dontAsk') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="handleKeepChinese"
        >
          {{ t('app.browserLocale.keepChinese') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="handleSwitch"
        >
          {{ t('app.browserLocale.switch') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
