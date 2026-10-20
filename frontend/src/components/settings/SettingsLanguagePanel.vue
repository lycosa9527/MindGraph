<script setup lang="ts">
/**
 * Language tab inside UserSettingsModal: interface, optional second line, AI language, canvas touch.
 * AI language follows the interface unless the user picks another language.
 * Each change is applied immediately. Drafts exist so opening the dialog does not rewrite prefs.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { ElCheckbox } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'
import BilingualUiSettingsSection from '@/components/settings/BilingualUiSettingsSection.vue'
import SettingsLanguagePreview from '@/components/settings/SettingsLanguagePreview.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { CanvasInputMode } from '@/config/canvasInputMode'
import { CANVAS_INPUT_MODES, CANVAS_INPUT_MODE_LABEL } from '@/config/canvasInputMode'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { formatGalleryLanguageMenuLabel } from '@/i18n/galleryLanguageMenuLabel'
import {
  getInterfaceLanguagePickerLocaleCount,
  getLocalesForInterfaceLanguagePicker,
  getPromptLanguageOptionsForPicker,
  matchedPromptLanguageForUiLocale,
} from '@/i18n/locales'
import { useAuthStore } from '@/stores/auth'
import { complementaryUiLocale } from '@/stores/bilingualUiPrefs'
import type { Language, PromptLanguage } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import '@/styles/settings-language-swiss.css'
import { MULTISCRIPT_SANS_STACK } from '@/utils/diagramNodeFontStack'

const props = defineProps<{
  /** True while the parent settings dialog is open. Reloads the current prefs on each open. */
  open: boolean
}>()

/** True while copying store values into the controls, so that copy is not saved again. */
let hydrating = false

const uiStore = useUIStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const draftUi = ref<Language>(uiStore.language)
const draftPrompt = ref<PromptLanguage>(uiStore.promptLanguage)
const draftCanvasInputMode = ref<CanvasInputMode>(uiStore.canvasInputMode)

const draftBilingualUiEnabled = ref(uiStore.bilingualUiEnabled)
const draftPresenterUiLocale = ref<Language>(uiStore.presenterUiLocale)
const matchPromptToInterface = ref(uiStore.matchPromptToUi)
/** LLM choice to restore when dual mode is turned off in this visit. */
const promptDraftBeforeBilingual = ref<{ match: boolean; prompt: PromptLanguage } | null>(null)

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
  const orderIndex = (code: string) => {
    const i = promptOpts.findIndex((p) => p.code === code)
    return i === -1 ? 9999 : i
  }
  const currentCodes = new Set<string>([draftUi.value, draftPresenterUiLocale.value])
  const byCode = new Map<string, ReturnType<typeof getLocalesForInterfaceLanguagePicker>[number]>()
  for (const code of currentCodes) {
    for (const row of getLocalesForInterfaceLanguagePicker(code, allow)) {
      byCode.set(row.code, row)
    }
  }
  const merged = Array.from(byCode.values())
  merged.sort((a, b) => orderIndex(a.code) - orderIndex(b.code) || a.code.localeCompare(b.code))
  return merged.map((u) => {
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

/** Diagram text in the preview: the AI language, which follows the interface when that box is checked. */
const previewContentLocale = computed(() =>
  matchPromptToInterface.value
    ? (matchedPromptLanguageForUiLocale(draftUi.value) ?? draftPrompt.value)
    : draftPrompt.value
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
function loadDraftsFromStore(): void {
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
  draftCanvasInputMode.value = uiStore.canvasInputMode
  draftBilingualUiEnabled.value = uiStore.bilingualUiEnabled
  const presenterLocale = uiStore.presenterUiLocale
  draftPresenterUiLocale.value =
    !allowSimplifiedChinesePicker.value && presenterLocale === 'zh' ? 'en' : presenterLocale
  matchPromptToInterface.value = uiStore.matchPromptToUi
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      return
    }
    hydrating = true
    loadDraftsFromStore()
    void ensureFontsForLanguageCode(draftPresenterUiLocale.value)
    void ensureFontsForLanguageCode(draftPrompt.value)
    void ensureFontsForLanguageCode(draftUi.value)
    void nextTick(() => {
      hydrating = false
    })
  },
  { immediate: true }
)

watch(draftPrompt, (code) => {
  if (props.open) {
    void ensureFontsForLanguageCode(code)
  }
})

watch(draftUi, (code) => {
  if (props.open) {
    void ensureFontsForLanguageCode(code)
  }
})

watch(draftPresenterUiLocale, (code) => {
  if (props.open) {
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

function ensureDistinctSecondaryLocale(): void {
  if (!draftBilingualUiEnabled.value) {
    return
  }
  if (draftPresenterUiLocale.value !== draftUi.value) {
    return
  }
  const next = complementaryUiLocale(draftUi.value, allowSimplifiedChinesePicker.value)
  if (next !== draftUi.value) {
    draftPresenterUiLocale.value = next
  }
}

function lockDraftPromptToInterface(): void {
  matchPromptToInterface.value = true
  const matched = matchedPromptLanguageForUiLocale(draftUi.value)
  if (matched !== null) {
    draftPrompt.value = matched
  }
}

watch(draftBilingualUiEnabled, (on, previous) => {
  if (hydrating) {
    return
  }
  if (on) {
    if (previous === false) {
      promptDraftBeforeBilingual.value = {
        match: matchPromptToInterface.value,
        prompt: draftPrompt.value,
      }
    }
    ensureDistinctSecondaryLocale()
    lockDraftPromptToInterface()
    return
  }
  if (previous !== true) {
    return
  }
  const snapshot = promptDraftBeforeBilingual.value
  promptDraftBeforeBilingual.value = null
  if (snapshot === null) {
    return
  }
  matchPromptToInterface.value = snapshot.match
  draftPrompt.value = snapshot.prompt
})

watch([draftUi, draftPresenterUiLocale], () => {
  ensureDistinctSecondaryLocale()
})

async function applyLanguageSettings(): Promise<boolean> {
  const ui = draftUi.value
  const promptForPersist: PromptLanguage = matchPromptToInterface.value
    ? (matchedPromptLanguageForUiLocale(ui) ?? draftPrompt.value)
    : draftPrompt.value
  if (authStore.isAuthenticated) {
    const ok = await authStore.saveLanguagePreferences(ui, promptForPersist, {
      matchPromptToUi: matchPromptToInterface.value,
      bilingualUiEnabled: draftBilingualUiEnabled.value,
      presenterUiLocale: draftPresenterUiLocale.value,
    })
    if (!ok) {
      return false
    }
  }
  uiStore.setBilingualUiEnabled(draftBilingualUiEnabled.value)
  uiStore.setPresenterUiLocale(draftPresenterUiLocale.value)
  uiStore.setMatchPromptToUi(matchPromptToInterface.value)
  uiStore.setLanguage(ui)
  if (!matchPromptToInterface.value) {
    uiStore.setPromptLanguage(promptForPersist)
  }
  uiStore.setCanvasInputMode(draftCanvasInputMode.value)
  uiStore.setUiLanguageExplicit(true)
  return true
}

let applyQueued = false
let applyRunning = false
let applyAgain = false

function scheduleApply(): void {
  if (!props.open || hydrating) {
    return
  }
  if (applyRunning) {
    applyAgain = true
    return
  }
  if (applyQueued) {
    return
  }
  applyQueued = true
  void nextTick(() => {
    applyQueued = false
    void runApply()
  })
}

async function runApply(): Promise<void> {
  if (!props.open || hydrating) {
    return
  }
  applyRunning = true
  const ok = await applyLanguageSettings()
  applyRunning = false
  if (!ok && props.open) {
    applyAgain = false
    hydrating = true
    loadDraftsFromStore()
    void nextTick(() => {
      hydrating = false
    })
    return
  }
  if (applyAgain) {
    applyAgain = false
    scheduleApply()
  }
}

watch(
  [
    draftUi,
    draftPrompt,
    draftCanvasInputMode,
    draftBilingualUiEnabled,
    draftPresenterUiLocale,
    matchPromptToInterface,
  ],
  () => {
    scheduleApply()
  }
)
</script>

<template>
  <div class="language-settings-swiss__split user-settings-tab-pad">
    <div class="language-settings-swiss__stack">
      <BilingualUiSettingsSection
        v-if="draftBilingualUiEnabled"
        v-model:enabled="draftBilingualUiEnabled"
      />
      <section class="language-settings-ui-picker">
        <div class="language-settings-swiss__kicker">
          <span>
            <I18nText
              :k="
                draftBilingualUiEnabled
                  ? 'settings.language.primaryLanguage'
                  : 'settings.language.interface'
              "
            />
          </span>
          <span class="language-settings-swiss__kicker-count">
            <I18nText
              k="settings.language.supportsCount"
              :params="{ n: interfaceLanguageOptionCount }"
            />
          </span>
        </div>
        <el-select
          v-model="draftUi"
          class="lang-settings-swiss-select interface-lang-select prompt-lang-select w-full"
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
                <span class="prompt-option-name">{{
                  formatGalleryLanguageMenuLabel(o.code, o.label)
                }}</span>
                <span class="prompt-option-en">{{ o.englishName }}</span>
              </span>
            </span>
          </el-option>
        </el-select>
      </section>

      <section v-if="draftBilingualUiEnabled">
        <div class="language-settings-swiss__kicker">
          <I18nText k="settings.language.secondaryLanguage" />
        </div>
        <el-select
          v-model="draftPresenterUiLocale"
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
                <span class="prompt-option-name">{{
                  formatGalleryLanguageMenuLabel(option.code, option.label)
                }}</span>
                <span class="prompt-option-en">{{ option.englishName }}</span>
              </span>
            </span>
          </el-option>
        </el-select>
        <p class="language-settings-swiss__hint">
          <I18nText k="settings.language.secondaryLanguageHint" />
        </p>
      </section>

      <BilingualUiSettingsSection
        v-if="!draftBilingualUiEnabled"
        v-model:enabled="draftBilingualUiEnabled"
      />

      <section v-if="!draftBilingualUiEnabled">
        <div class="language-settings-swiss__kicker">
          <span><I18nText k="settings.language.prompt" /></span>
          <span class="language-settings-swiss__kicker-count">
            <I18nText
              k="settings.language.supportsCount"
              :params="{ n: promptLanguageOptionCount }"
            />
          </span>
        </div>
        <el-select
          v-model="draftPrompt"
          class="lang-settings-swiss-select prompt-lang-select language-settings-swiss__follow-select w-full"
          filterable
          :disabled="matchPromptToInterface"
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
                <span class="prompt-option-name">{{
                  formatGalleryLanguageMenuLabel(o.code, o.label)
                }}</span>
                <span class="prompt-option-en">{{ o.englishName }}</span>
              </span>
            </span>
          </el-option>
        </el-select>
        <ElCheckbox
          v-model="matchPromptToInterface"
          class="language-settings-swiss__match-prompt"
        >
          <I18nText k="settings.language.matchPrompt" />
        </ElCheckbox>
      </section>
    </div>
    <div class="language-settings-swiss__preview-slot">
      <SettingsLanguagePreview
        :ui-locale="draftUi"
        :presenter-locale="draftPresenterUiLocale"
        :bilingual="draftBilingualUiEnabled"
        :content-locale="previewContentLocale"
      />
    </div>
    <section class="language-settings-swiss__canvas-span">
      <div class="language-settings-swiss__kicker">
        <span><I18nText k="settings.language.canvasInputMode" /></span>
      </div>
      <div
        class="language-settings-canvas-segmented"
        role="radiogroup"
        :aria-label="t('settings.language.canvasInputMode')"
      >
        <button
          v-for="mode in CANVAS_INPUT_MODES"
          :key="mode"
          type="button"
          role="radio"
          class="language-settings-canvas-segment"
          :class="{ 'is-active': draftCanvasInputMode === mode }"
          :aria-checked="draftCanvasInputMode === mode"
          @click="draftCanvasInputMode = mode"
        >
          <I18nText :k="CANVAS_INPUT_MODE_LABEL[mode]" />
        </button>
      </div>
      <p class="language-settings-swiss__hint">
        <I18nText k="settings.language.canvasInputHint" />
      </p>
    </section>
  </div>
</template>

<style scoped>
.language-settings-swiss__split {
  display: grid;
  grid-template-columns: 15.5rem minmax(0, 1fr);
  grid-template-areas:
    'settings preview'
    'canvas canvas';
  gap: 0.75rem;
  align-items: stretch;
}

.language-settings-swiss__stack {
  grid-area: settings;
}

.language-settings-swiss__preview-slot {
  grid-area: preview;
  min-width: 0;
  min-height: 0;
}

.language-settings-swiss__canvas-span {
  grid-area: canvas;
}

@media (max-width: 720px) {
  .language-settings-swiss__split {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      'settings'
      'preview'
      'canvas';
  }
}

/* Dialog checkbox/title/body wrapping is global (`styles/index.css`); overrides here
 * are limited to searchable language selects used only in this modal. */
.language-settings-swiss__match-prompt {
  margin-top: 0.75rem;
}

.prompt-lang-select :deep(.el-select__wrapper) {
  min-width: 0;
}

.prompt-lang-select :deep(.el-select__wrapper.is-focused) {
  border-color: #78716c;
  box-shadow: 0 0 0 1px #d6d3d1;
}

.prompt-lang-select :deep(.el-select__caret) {
  color: #78716c;
}

.prompt-lang-select :deep(.el-select__input) {
  caret-color: #1c1917;
  font-family: inherit;
}

.prompt-lang-select :deep(.el-select__selection) {
  font-family: v-bind('multiscriptFontFamily');
}

.prompt-lang-select :deep(.el-select__selected-item) {
  font-family: inherit;
  min-width: 0;
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
