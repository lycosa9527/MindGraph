<script setup lang="ts">
/**
 * Quick UI + prompt language switch for MindGraph landing — enables sync and updates both.
 */
import { computed } from 'vue'

import { ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, Languages } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import {
  getLocalesForInterfaceLanguagePicker,
  getPromptLanguageOptionsForPicker,
} from '@/i18n/locales'
import { useAuthStore } from '@/stores/auth'
import type { Language } from '@/stores/ui'
import { useUIStore } from '@/stores/ui'

const props = withDefaults(
  defineProps<{
    /** Header row next to Import vs floating corner on international landing */
    variant?: 'header' | 'floating'
  }>(),
  { variant: 'header' }
)

const uiStore = useUIStore()
const authStore = useAuthStore()
const { t } = useLanguage()

const languageRows = computed(() => {
  const allow = uiStore.languagePolicyAllowZh
  const promptOpts = getPromptLanguageOptionsForPicker(allow)
  const enabled = getLocalesForInterfaceLanguagePicker(uiStore.language, allow)
  const orderIndex = (code: string) => {
    const i = promptOpts.findIndex((p) => p.code === code)
    return i === -1 ? 9999 : i
  }
  enabled.sort((a, b) => orderIndex(a.code) - orderIndex(b.code) || a.code.localeCompare(b.code))
  return enabled.map((u) => {
    const prompt = promptOpts.find((p) => p.code === u.code)
    const label = prompt ? prompt.label : u.nativeName
    const code = u.code as Language
    return {
      code,
      label,
    }
  })
})

const buttonLabelShort = computed(() => uiStore.language)

function onSelect(code: string): void {
  const lang = code as Language
  uiStore.setMatchPromptToUi(true)
  uiStore.setLanguage(lang)
  uiStore.setUiLanguageExplicit(true)
  void ensureFontsForLanguageCode(lang)
  const promptCode = uiStore.promptLanguage
  if (authStore.isAuthenticated) {
    void authStore.saveLanguagePreferences(lang, promptCode, { matchPromptToUi: true })
  }
}
</script>

<template>
  <div
    class="mindgraph-lang-switcher-root"
    :class="{ 'mindgraph-lang-switcher-root--floating': props.variant === 'floating' }"
  >
    <ElDropdown
      trigger="click"
      popper-class="mindgraph-lang-switcher-popper"
      @command="onSelect"
    >
      <ElButton
        :class="
          props.variant === 'floating'
            ? 'mindgraph-lang-switcher mindgraph-lang-switcher--floating'
            : 'mindgraph-lang-switcher mindgraph-lang-switcher--header'
        "
        size="small"
        :title="t('mindgraphLanding.languageMenuTitle')"
        :aria-label="t('mindgraphLanding.languageMenuTitle')"
      >
        <Languages class="w-[17px] h-[17px] shrink-0" />
        <span class="mindgraph-lang-switcher__code">{{ buttonLabelShort }}</span>
      </ElButton>
      <template #dropdown>
        <ElDropdownMenu
          class="mindgraph-lang-switcher__menu max-h-[min(420px,70vh)] overflow-y-auto"
        >
          <ElDropdownItem
            v-for="row in languageRows"
            :key="row.code"
            :command="row.code"
          >
            <span class="mindgraph-lang-switcher__row">
              <span
                class="mindgraph-lang-switcher__label"
                dir="auto"
                :lang="row.code"
              >
                {{ row.label }}
              </span>
              <Check
                v-if="row.code === uiStore.language"
                class="mindgraph-lang-switcher__check w-4 h-4 shrink-0 opacity-70"
                aria-hidden="true"
              />
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
  </div>
</template>

<style scoped>
.mindgraph-lang-switcher-root--floating {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 21;
}
.mindgraph-lang-switcher.mindgraph-lang-switcher--header {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

.mindgraph-lang-switcher.mindgraph-lang-switcher--floating {
  --el-button-bg-color: #ffffff;
  --el-button-border-color: #e7e5e4;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-hover-border-color: #d6d3d1;
  --el-button-text-color: #44403c;
  font-weight: 500;
  border-radius: 9999px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.mindgraph-lang-switcher__code {
  margin-left: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  max-width: 52px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Centered label; checkmark in the gutter so text stays visually centered */
.mindgraph-lang-switcher__row {
  position: relative;
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 5px 20px;
  min-height: 1.35em;
}

.mindgraph-lang-switcher__label {
  display: block;
  width: 100%;
  text-align: center;
}

.mindgraph-lang-switcher__check {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
}

.dark .mindgraph-lang-switcher.mindgraph-lang-switcher--floating {
  --el-button-bg-color: #1f2937;
  --el-button-border-color: #374151;
  --el-button-hover-bg-color: #374151;
  --el-button-text-color: #f9fafb;
}
</style>

<!-- Teleported dropdown — width lives on popper, not scoped subtree -->
<style>
.mindgraph-lang-switcher-popper.el-popper {
  /* firm width: menu never wider than the popper */
  width: min(180px, calc(100vw - 24px)) !important;
  max-width: min(180px, calc(100vw - 24px)) !important;
  box-sizing: border-box !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.mindgraph-lang-switcher-popper .el-dropdown-menu {
  /* fill the popper exactly; no independent fixed px width */
  width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  /* pre-allocate scrollbar gutter so vertical bar never shifts content */
  scrollbar-gutter: stable;
}

.mindgraph-lang-switcher-popper .el-dropdown-menu__item {
  box-sizing: border-box;
  width: 100%;
  padding: 0 !important;
  border-radius: 6px;
  transition:
    background 0.12s,
    color 0.12s;
}

.mindgraph-lang-switcher-popper .el-dropdown-menu__item:hover,
.mindgraph-lang-switcher-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.mindgraph-lang-switcher-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

/* Inner row: centred label + gutter checkmark */
.mindgraph-lang-switcher-popper .mindgraph-lang-switcher__row {
  box-sizing: border-box;
  width: 100%;
  padding: 7px 24px 7px 10px;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  overflow: hidden;
}

.mindgraph-lang-switcher-popper .el-dropdown-menu__item:hover .mindgraph-lang-switcher__row,
.mindgraph-lang-switcher-popper .el-dropdown-menu__item:focus .mindgraph-lang-switcher__row {
  color: #1c1917;
}
</style>
