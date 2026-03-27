<script setup lang="ts">
/**
 * First-visit hint when browser is en/az but UI is still default Chinese.
 */
import { computed, ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { loadLocaleMessages, setI18nLocale } from '@/i18n'
import { SUPPORTED_UI_LOCALES } from '@/i18n/locales'
import type { Language } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

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
    targetLocale.value = nav.startsWith('az') ? 'az' : 'en'
  }
})

async function handleSwitch(): Promise<void> {
  const loc = targetLocale.value
  await loadLocaleMessages(loc)
  setI18nLocale(loc)
  uiStore.setLanguage(loc)
  uiStore.setPromptLanguage(loc)
  uiStore.setUiLanguageExplicit(true)
  visible.value = false
}

function handleKeepChinese(): void {
  uiStore.setUiLanguageExplicit(true)
  visible.value = false
}

function handleDontAsk(): void {
  uiStore.setBrowserLocaleHintDismissed(true)
  visible.value = false
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="t('app.browserLocale.title')"
    width="min(400px, 92vw)"
    destroy-on-close
  >
    <p class="text-stone-700 dark:text-stone-300 text-sm leading-relaxed">
      {{ t('app.browserLocale.body', { name: targetDisplayName }) }}
    </p>
    <template #footer>
      <div class="flex flex-wrap gap-2 justify-end">
        <el-button @click="handleDontAsk">
          {{ t('app.browserLocale.dontAsk') }}
        </el-button>
        <el-button @click="handleKeepChinese">
          {{ t('app.browserLocale.keepChinese') }}
        </el-button>
        <el-button
          type="primary"
          @click="handleSwitch"
        >
          {{ t('app.browserLocale.switch') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
