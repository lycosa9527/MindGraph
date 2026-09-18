<script setup lang="ts">
/**
 * Bilingual UI chrome toggle. When on, primary + second language pickers replace
 * the standalone interface-language dropdown.
 */
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { Language } from '@/stores/ui'

const { t } = useLanguage()

defineProps<{
  uiLanguageOptions: {
    code: Language
    label: string
    englishName: string
  }[]
  optionCount: number
}>()

const draftEnabled = defineModel<boolean>('enabled', { required: true })
const draftPrimary = defineModel<Language>('primary', { required: true })
const draftSecondary = defineModel<Language>('secondary', { required: true })

function languageSelectDisplayLabel(option: { code: string; label: string }): string {
  return `${option.label} (${option.code})`
}
</script>

<template>
  <section>
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
    <p class="language-settings-swiss__hint">
      <I18nText k="settings.language.bilingualUiHint" />
    </p>

    <template v-if="draftEnabled">
      <div class="language-settings-swiss__kicker language-settings-swiss__kicker--spaced">
        <I18nText k="settings.language.primaryLanguage" />
        <span class="language-settings-swiss__kicker-count">
          <I18nText
            k="settings.language.supportsCount"
            :params="{ n: optionCount }"
          />
        </span>
      </div>
      <el-select
        v-model="draftPrimary"
        class="lang-settings-swiss-select interface-lang-select prompt-lang-select w-full"
        filterable
        :placeholder="t('settings.language.promptSelectPlaceholder')"
        popper-class="prompt-lang-select-popper"
      >
        <el-option
          v-for="option in uiLanguageOptions"
          :key="`primary-${option.code}`"
          :label="languageSelectDisplayLabel(option)"
          :value="option.code"
        >
          <span
            class="prompt-option-row"
            dir="auto"
            :lang="option.code"
          >
            <span class="prompt-option-code">{{ option.code }}</span>
            <span class="prompt-option-text">
              <span class="prompt-option-name">{{ option.label }}</span>
              <span class="prompt-option-en">{{ option.englishName }}</span>
            </span>
          </span>
        </el-option>
      </el-select>
      <p class="language-settings-swiss__hint">
        <I18nText k="settings.language.primaryLanguageHint" />
      </p>

      <div class="language-settings-swiss__kicker language-settings-swiss__kicker--spaced">
        <I18nText k="settings.language.secondaryLanguage" />
      </div>
      <el-select
        v-model="draftSecondary"
        class="lang-settings-swiss-select interface-lang-select prompt-lang-select w-full"
        filterable
        :placeholder="t('settings.language.promptSelectPlaceholder')"
        popper-class="prompt-lang-select-popper"
      >
        <el-option
          v-for="option in uiLanguageOptions"
          :key="`secondary-${option.code}`"
          :label="languageSelectDisplayLabel(option)"
          :value="option.code"
        >
          <span
            class="prompt-option-row"
            dir="auto"
            :lang="option.code"
          >
            <span class="prompt-option-code">{{ option.code }}</span>
            <span class="prompt-option-text">
              <span class="prompt-option-name">{{ option.label }}</span>
              <span class="prompt-option-en">{{ option.englishName }}</span>
            </span>
          </span>
        </el-option>
      </el-select>
      <p class="language-settings-swiss__hint">
        <I18nText k="settings.language.secondaryLanguageHint" />
      </p>
    </template>
  </section>
</template>
