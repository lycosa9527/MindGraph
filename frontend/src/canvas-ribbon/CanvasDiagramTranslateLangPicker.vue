<script setup lang="ts">
/**
 * New-canvas status-bar language picker — gallery menu style, starts a temp translate.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, Languages } from '@lucide/vue'

import '@/components/mindgraph/mindgraphLangSwitcher.css'
import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import { useCanvasDiagramTranslate } from '@/composables/canvasToolbar/useCanvasDiagramTranslate'
import { useLanguage } from '@/composables/core/useLanguage'
import { getGalleryLanguageMenuRows } from '@/i18n/galleryLanguageMenuRows'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useUIStore } from '@/stores/ui'

const { t } = useLanguage()
const uiStore = useUIStore()
const translateUi = useDiagramTranslateUiStore()
const { pendingTargetLanguage, hasPendingTranslate, phase: translatePhase } = storeToRefs(translateUi)
const { armAndStartTranslate, aiBlockedByCollab } = useCanvasDiagramTranslate()

const languageRows = computed(() =>
  getGalleryLanguageMenuRows(uiStore.language, uiStore.languagePolicyAllowZh)
)

const triggerCode = computed(() => pendingTargetLanguage.value ?? '')

function onSelect(code: string): void {
  armAndStartTranslate(code)
}
</script>

<template>
  <ElDropdown
    v-if="!aiBlockedByCollab"
    trigger="click"
    placement="top-end"
    popper-class="mindgraph-lang-switcher-popper"
    data-testid="mindmap-ribbon-translate-lang"
    @command="onSelect"
  >
    <LlmPhaseRing
      :phase="translatePhase"
      streaming-variant="primary"
      border-radius="6px"
    >
      <button
        type="button"
        class="mm-status__zoom-btn mm-status__translate-btn"
        :class="{ 'is-translating': hasPendingTranslate }"
        :title="t('canvas.toolbar.translateLabelTargetLanguage')"
        :aria-label="t('canvas.toolbar.translateLabelTargetLanguage')"
      >
        {{ t('canvas.toolbar.moreAppTranslateLabel') }}
        <Languages
          class="h-3.5 w-3.5"
          :stroke-width="2"
        />
        <span
          v-if="triggerCode"
          class="mm-status__translate-code"
          >{{ triggerCode }}</span
        >
      </button>
    </LlmPhaseRing>
    <template #dropdown>
      <ElDropdownMenu class="mindgraph-lang-switcher__menu max-h-[min(420px,70vh)] overflow-y-auto">
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
              v-if="row.code === pendingTargetLanguage"
              class="mindgraph-lang-switcher__check w-4 h-4 shrink-0 opacity-70"
              aria-hidden="true"
            />
          </span>
        </ElDropdownItem>
      </ElDropdownMenu>
    </template>
  </ElDropdown>
</template>
