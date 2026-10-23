<script setup lang="ts">
/**
 * Dual-language Off/On control.
 * The parent places it above the primary language while dual mode is on,
 * and shows the second language picker itself.
 */
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const { t } = useLanguage()

const draftEnabled = defineModel<boolean>('enabled', { required: true })
</script>

<template>
  <section class="language-settings-bilingual-toggle">
    <div class="language-settings-swiss__kicker">
      <I18nText k="settings.language.bilingualUi" />
    </div>
    <div
      class="language-settings-canvas-segmented"
      role="radiogroup"
      :aria-label="t('settings.language.bilingualUi')"
    >
      <button
        type="button"
        role="radio"
        class="language-settings-canvas-segment"
        :class="{ 'is-active': !draftEnabled }"
        :aria-checked="!draftEnabled"
        @click="draftEnabled = false"
      >
        <I18nText k="settings.language.bilingualUiOff" />
      </button>
      <button
        type="button"
        role="radio"
        class="language-settings-canvas-segment"
        :class="{ 'is-active': draftEnabled }"
        :aria-checked="draftEnabled"
        @click="draftEnabled = true"
      >
        <I18nText k="settings.language.bilingualUiOn" />
      </button>
    </div>
  </section>
</template>
