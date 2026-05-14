<script setup lang="ts">
/**
 * Language & prompt language settings (interface vs LLM prompt language).
 */
import { computed, ref, watch } from 'vue'

import { ElCheckbox } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import {
  getInterfaceLanguagePickerLocaleCount,
  getLocalesForInterfaceLanguagePicker,
  getPromptLanguageOptionsForPicker,
  matchedPromptLanguageForUiLocale,
} from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import type { Language, PromptLanguage } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import { MULTISCRIPT_SANS_STACK } from '@/utils/diagramNodeFontStack'

const visible = defineModel<boolean>({ required: true })

const uiStore = useUIStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const draftUi = ref<Language>(uiStore.language)
const draftPrompt = ref<PromptLanguage>(uiStore.promptLanguage)
const matchPromptToInterface = ref(uiStore.matchPromptToUi)

const allowSimplifiedChinesePicker = computed(() => uiStore.languagePolicyAllowZh)

/**
 * Interface language uses the same searchable dropdown as prompt language.
 * Rows come from translated UI locales (Tier 1–2 + primary); labels/search match the prompt registry when codes align.
 */
function buildUiLanguageSelectRows(): {
  code: Language
  label: string
  englishName: string
  search: string[]
}[] {
  const allow = allowSimplifiedChinesePicker.value
  const promptOpts = getPromptLanguageOptionsForPicker(allow)
  const enabled = getLocalesForInterfaceLanguagePicker(draftUi.value, allow)
  const orderIndex = (code: string) => {
    const i = promptOpts.findIndex((p) => p.code === code)
    return i === -1 ? 9999 : i
  }
  enabled.sort((a, b) => orderIndex(a.code) - orderIndex(b.code) || a.code.localeCompare(b.code))
  return enabled.map((u) => {
    const prompt = promptOpts.find((p) => p.code === u.code)
    if (prompt) {
      return {
        code: u.code as Language,
        label: prompt.label,
        englishName: prompt.englishName,
        search: prompt.search,
      }
    }
    return {
      code: u.code as Language,
      label: u.nativeName,
      englishName: u.englishName,
      search: [] as string[],
    }
  })
}

const uiLanguageOptions = computed(() => buildUiLanguageSelectRows())

const promptLangOptionsFiltered = computed(() =>
  getPromptLanguageOptionsForPicker(allowSimplifiedChinesePicker.value)
)

const interfaceLanguageOptionCount = computed(() =>
  getInterfaceLanguagePickerLocaleCount(allowSimplifiedChinesePicker.value)
)
const promptLanguageOptionCount = computed(
  () => getPromptLanguageOptionsForPicker(allowSimplifiedChinesePicker.value).length
)

/**
 * el-option `label` is shown in the collapsed select and used by filterable matching.
 * Use a short line only — long concatenations (code + EN + native + search) were
 * incorrectly shown as the selected value.
 */
function languageSelectDisplayLabel(o: { code: string; label: string }): string {
  return `${o.label} (${o.code})`
}

/** Same stack as diagram nodes; v-bind in style below. */
const multiscriptFontFamily = MULTISCRIPT_SANS_STACK

/**
 * Prompt-language dropdown lists ~149 native names; fonts load per selected code.
 * While browsing, OS fonts fill unsupported scripts (product tradeoff).
 */
watch(visible, (v) => {
  if (v) {
    let ui = uiStore.language
    let pr = uiStore.promptLanguage
    if (!allowSimplifiedChinesePicker.value) {
      if (ui === 'zh') {
        ui = 'en'
      }
      if (pr === 'zh') {
        pr = 'en'
      }
    }
    draftUi.value = ui
    draftPrompt.value = pr
    matchPromptToInterface.value = uiStore.matchPromptToUi
    void ensureFontsForLanguageCode(draftPrompt.value)
    void ensureFontsForLanguageCode(draftUi.value)
  }
})

watch(draftPrompt, (code) => {
  if (visible.value) {
    void ensureFontsForLanguageCode(code)
  }
})

watch(draftUi, (code) => {
  if (visible.value) {
    void ensureFontsForLanguageCode(code)
  }
})

watch(
  () => draftUi.value,
  (ui) => {
    if (matchPromptToInterface.value) {
      const matched = matchedPromptLanguageForUiLocale(ui)
      if (matched !== null) {
        draftPrompt.value = matched
      }
    }
  }
)

watch(matchPromptToInterface, (on) => {
  if (on) {
    const m = matchedPromptLanguageForUiLocale(draftUi.value)
    draftPrompt.value = m !== null ? m : draftPrompt.value
  }
})

async function save(): Promise<void> {
  const ui = draftUi.value
  const promptForPersist: PromptLanguage = matchPromptToInterface.value
    ? (matchedPromptLanguageForUiLocale(ui) ?? draftPrompt.value)
    : draftPrompt.value
  if (authStore.isAuthenticated) {
    const ok = await authStore.saveLanguagePreferences(ui, promptForPersist, {
      matchPromptToUi: matchPromptToInterface.value,
    })
    if (!ok) {
      return
    }
  }
  uiStore.setMatchPromptToUi(matchPromptToInterface.value)
  uiStore.setLanguage(ui)
  if (!matchPromptToInterface.value) {
    uiStore.setPromptLanguage(promptForPersist)
  }
  uiStore.setUiLanguageExplicit(true)
  visible.value = false
}

function onClose(): void {
  visible.value = false
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="t('settings.language.title')"
    width="min(480px, 92vw)"
    destroy-on-close
    @close="onClose"
  >
    <div class="space-y-5">
      <div>
        <ElCheckbox v-model="matchPromptToInterface">
          {{ t('settings.language.matchPrompt') }}
        </ElCheckbox>
      </div>
      <div>
        <div
          class="text-sm text-stone-600 dark:text-stone-400 mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
        >
          <span>{{ t('settings.language.interface') }}</span>
          <span class="text-xs text-stone-400 dark:text-stone-500 font-normal">
            {{ t('settings.language.supportsCount', { n: interfaceLanguageOptionCount }) }}
          </span>
        </div>
        <el-select
          v-model="draftUi"
          class="interface-lang-select prompt-lang-select w-full"
          filterable
          :placeholder="t('settings.language.promptSelectPlaceholder')"
          popper-class="prompt-lang-select-popper"
        >
          <el-option
            v-for="o in uiLanguageOptions"
            :key="o.code"
            :label="languageSelectDisplayLabel(o)"
            :value="o.code"
          >
            <span
              class="prompt-option-row"
              dir="auto"
              :lang="o.code"
            >
              <span class="prompt-option-code">{{ o.code }}</span>
              <span class="prompt-option-text">
                <span class="prompt-option-name">{{ o.label }}</span>
                <span class="prompt-option-en">{{ o.englishName }}</span>
              </span>
            </span>
          </el-option>
        </el-select>
      </div>
      <div>
        <div
          class="text-sm text-stone-600 dark:text-stone-400 mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5"
        >
          <span>{{ t('settings.language.prompt') }}</span>
          <span class="text-xs text-stone-400 dark:text-stone-500 font-normal">
            {{ t('settings.language.supportsCount', { n: promptLanguageOptionCount }) }}
          </span>
        </div>
        <el-select
          v-model="draftPrompt"
          class="prompt-lang-select w-full"
          :disabled="matchPromptToInterface"
          filterable
          :placeholder="t('settings.language.promptSelectPlaceholder')"
          popper-class="prompt-lang-select-popper"
        >
          <el-option
            v-for="o in promptLangOptionsFiltered"
            :key="o.code"
            :label="languageSelectDisplayLabel(o)"
            :value="o.code"
          >
            <span
              class="prompt-option-row"
              dir="auto"
              :lang="o.code"
            >
              <span class="prompt-option-code">{{ o.code }}</span>
              <span class="prompt-option-text">
                <span class="prompt-option-name">{{ o.label }}</span>
                <span class="prompt-option-en">{{ o.englishName }}</span>
              </span>
            </span>
          </el-option>
        </el-select>
      </div>
    </div>
    <template #footer>
      <el-button @click="onClose">
        {{ t('common.cancel') }}
      </el-button>
      <el-button
        type="primary"
        @click="save"
      >
        {{ t('common.save') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
/* Dialog checkbox/title/body wrapping is global (`styles/index.css`); overrides here
 * are limited to searchable language selects used only in this modal. */
.prompt-lang-select :deep(.el-select__wrapper) {
  min-width: 0;
}

.prompt-lang-select :deep(.el-select__selection) {
  font-family: v-bind('multiscriptFontFamily');
}

.prompt-lang-select :deep(.el-select__selected-item) {
  font-family: inherit;
  min-width: 0;
}

.prompt-lang-select :deep(.el-select__input) {
  font-family: inherit;
}

/*
 * Keep Element Plus absolute `.el-select__placeholder` for filterable + value; forcing
 * `position: relative` stacks the label under the input and shows a spurious blank row.
 */
.prompt-lang-select :deep(.el-select__placeholder) {
  font-family: inherit;
}
</style>

<!-- Dropdown is teleported; target via popper-class -->
<style>
/*
 * Element Plus applies `popper-class` to both the tooltip shell (`.el-select__popper`)
 * and the inner `.el-select-dropdown`. Swiss chrome lives only on the outer popper;
 * the inner panel is reset so borders/padding are not doubled.
 */
.el-select__popper.prompt-lang-select-popper.el-popper {
  box-sizing: border-box !important;
  max-width: min(92vw, 32rem) !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  background: #ffffff !important;
  overflow: hidden !important;
}

.dark .el-select__popper.prompt-lang-select-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.el-select-dropdown.prompt-lang-select-popper {
  max-width: 100% !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.prompt-lang-select-popper .el-select-dropdown__list {
  padding: 0 !important;
  margin: 0 !important;
  scrollbar-gutter: stable;
}

.prompt-lang-select-popper .el-select-dropdown__item {
  height: auto !important;
  min-height: 2.25rem;
  line-height: 1.25;
  padding: 0.35rem 12px 0.35rem 10px !important;
  border-radius: 6px;
  font-family: v-bind('multiscriptFontFamily');
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: break-word;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.dark .prompt-lang-select-popper .el-select-dropdown__item {
  color: #d6d3d1;
}

.prompt-lang-select-popper .el-select-dropdown__item.is-hovering,
.prompt-lang-select-popper .el-select-dropdown__item:hover {
  background: #f5f5f4 !important;
  color: #1c1917 !important;
}

.dark .prompt-lang-select-popper .el-select-dropdown__item.is-hovering,
.dark .prompt-lang-select-popper .el-select-dropdown__item:hover {
  background: #374151 !important;
  color: #f9fafb !important;
}

.prompt-lang-select-popper .el-select-dropdown__item:active {
  background: #e7e5e4 !important;
}

.dark .prompt-lang-select-popper .el-select-dropdown__item:active {
  background: #4b5563 !important;
}

.prompt-lang-select-popper .el-select-dropdown__item.is-selected {
  font-weight: 600 !important;
  color: #1c1917 !important;
  background: #f5f5f4 !important;
}

.dark .prompt-lang-select-popper .el-select-dropdown__item.is-selected {
  color: #f9fafb !important;
  background: #374151 !important;
}

.prompt-lang-select-popper .el-select-dropdown__item.is-disabled {
  opacity: 0.55;
}

.prompt-lang-select-popper .prompt-option-row {
  display: grid;
  grid-template-columns: minmax(3.25rem, max-content) minmax(0, 1fr);
  column-gap: 0.75rem;
  align-items: start;
  width: 100%;
  text-align: start;
}

.prompt-lang-select-popper .prompt-option-text {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.prompt-lang-select-popper .prompt-option-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
}

.prompt-lang-select-popper .prompt-option-name {
  min-width: 0;
  font-size: 0.875rem;
  color: var(--el-text-color-primary);
  word-break: break-word;
  overflow-wrap: break-word;
}

.prompt-lang-select-popper .prompt-option-en {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  line-height: 1.2;
  word-break: break-word;
  overflow-wrap: break-word;
}
</style>
