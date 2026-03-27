<script setup lang="ts">
/**
 * Language & prompt language settings (interface vs LLM prompt language).
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ElCheckbox } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { PROMPT_LANGUAGE_OPTIONS, getLocalesForInterfaceLanguagePicker } from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import type { Language, PromptLanguage, UiVersion } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'
import { MULTISCRIPT_SANS_STACK } from '@/utils/diagramNodeFontStack'

const visible = defineModel<boolean>({ required: true })

const router = useRouter()
const uiStore = useUIStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const draftUi = ref<Language>(uiStore.language)
const draftPrompt = ref<PromptLanguage>(uiStore.promptLanguage)
const draftVersion = ref<UiVersion>(uiStore.uiVersion)
const promptLangOptions = PROMPT_LANGUAGE_OPTIONS
const matchPromptToInterface = ref(uiStore.matchPromptToUi)

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
  const enabled = getLocalesForInterfaceLanguagePicker(draftUi.value)
  const orderIndex = (code: string) => {
    const i = PROMPT_LANGUAGE_OPTIONS.findIndex((p) => p.code === code)
    return i === -1 ? 9999 : i
  }
  enabled.sort((a, b) => orderIndex(a.code) - orderIndex(b.code) || a.code.localeCompare(b.code))
  return enabled.map((u) => {
    const prompt = PROMPT_LANGUAGE_OPTIONS.find((p) => p.code === u.code)
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

const interfaceLanguageOptionCount = computed(() => uiLanguageOptions.value.length)
const promptLanguageOptionCount = computed(() => promptLangOptions.length)

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
    draftUi.value = uiStore.language
    draftPrompt.value = uiStore.promptLanguage
    draftVersion.value = uiStore.uiVersion
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
      draftPrompt.value = ui
    }
  }
)

watch(matchPromptToInterface, (on) => {
  if (on) {
    draftPrompt.value = draftUi.value
  }
})

async function save(): Promise<void> {
  const ui = draftUi.value
  const prompt = matchPromptToInterface.value ? draftUi.value : draftPrompt.value
  const version = draftVersion.value
  if (authStore.isAuthenticated) {
    const ok = await authStore.saveLanguagePreferences(ui, prompt, version)
    if (!ok) {
      return
    }
  }
  uiStore.setMatchPromptToUi(matchPromptToInterface.value)
  uiStore.setLanguage(ui)
  if (!matchPromptToInterface.value) {
    uiStore.setPromptLanguage(prompt)
  }
  const versionChanged = version !== uiStore.uiVersion
  uiStore.setUiVersion(version)
  uiStore.setUiLanguageExplicit(true)
  visible.value = false

  if (versionChanged) {
    const target = version === 'international' ? '/mindgraph' : '/mindmate'
    router.push(target)
  }
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
    class="language-settings-dialog"
    @close="onClose"
  >
    <div class="space-y-5">
      <div>
        <div class="text-sm text-stone-600 dark:text-stone-400 mb-2">
          {{ t('settings.version.title') }}
        </div>
        <el-radio-group
          v-model="draftVersion"
          class="version-group flex w-full gap-3"
        >
          <el-radio value="chinese">
            {{ t('settings.version.chinese') }}
          </el-radio>
          <el-radio value="international">
            {{ t('settings.version.international') }}
          </el-radio>
        </el-radio-group>
      </div>
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
            v-for="o in promptLangOptions"
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
.prompt-lang-select :deep(.el-select__selected-item) {
  font-family: v-bind('multiscriptFontFamily');
}
</style>

<!-- Dropdown is teleported; target via popper-class -->
<style>
.prompt-lang-select-popper .el-select-dropdown__item {
  height: auto !important;
  min-height: 2.25rem;
  line-height: 1.25;
  padding-top: 0.35rem;
  padding-bottom: 0.35rem;
  font-family: v-bind('multiscriptFontFamily');
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
}

.prompt-lang-select-popper .prompt-option-en {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  line-height: 1.2;
}
</style>
