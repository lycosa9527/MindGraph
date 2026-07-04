<script setup lang="ts">
/**
 * Export option toggles — Swiss stone segmented controls (AdminSwissSegmented fit).
 */
import { computed } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type {
  CanvasExportAnswerMode,
  CanvasExportColorMode,
  CanvasExportLayout,
  CanvasExportOptions,
} from '@/config/canvasExportOptions'
import { useDiagramStore } from '@/stores'

const options = defineModel<CanvasExportOptions>({ required: true })

const { t } = useLanguage()
const diagramStore = useDiagramStore()

const showAnswerOption = computed(
  () => diagramStore.isLearningSheet && diagramStore.hasBlankedLearningSheetNodes()
)

const colorMode = computed({
  get: () => options.value.colorMode,
  set: (value: CanvasExportColorMode) => {
    options.value = { ...options.value, colorMode: value }
  },
})

const layout = computed({
  get: () => options.value.layout,
  set: (value: CanvasExportLayout) => {
    options.value = { ...options.value, layout: value }
  },
})

const answerMode = computed({
  get: () => options.value.answerMode,
  set: (value: CanvasExportAnswerMode) => {
    options.value = { ...options.value, answerMode: value }
  },
})

const colorOptions = computed(() => [
  { label: t('canvas.exportOptions.colorColored'), value: 'color' as const },
  { label: t('canvas.exportOptions.colorWireframe'), value: 'wireframe' as const },
])

const layoutOptions = computed(() => [
  { label: t('canvas.exportOptions.layoutLandscape'), value: 'landscape' as const },
  { label: t('canvas.exportOptions.layoutPortrait'), value: 'portrait' as const },
])

const answerOptions = computed(() => [
  { label: t('canvas.exportOptions.answerInclude'), value: 'include' as const },
  { label: t('canvas.exportOptions.answerExclude'), value: 'exclude' as const },
])
</script>

<template>
  <div class="mm-export-options">
    <div class="mm-export-options__row">
      <span class="mm-export-options__label">{{ t('canvas.exportOptions.colorLabel') }}</span>
      <AdminSwissSegmented
        v-model="colorMode"
        fit
        :options="colorOptions"
        :aria-label="t('canvas.exportOptions.colorLabel')"
      />
    </div>

    <div class="mm-export-options__row">
      <span class="mm-export-options__label">{{ t('canvas.exportOptions.layoutLabel') }}</span>
      <AdminSwissSegmented
        v-model="layout"
        fit
        :options="layoutOptions"
        :aria-label="t('canvas.exportOptions.layoutLabel')"
      />
    </div>

    <div
      v-if="showAnswerOption"
      class="mm-export-options__row"
    >
      <span class="mm-export-options__label">{{ t('canvas.exportOptions.answerLabel') }}</span>
      <AdminSwissSegmented
        v-model="answerMode"
        fit
        :options="answerOptions"
        :aria-label="t('canvas.exportOptions.answerLabel')"
      />
    </div>
  </div>
</template>

<style scoped>
.mm-export-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--swiss-border, #e7e5e4);
}

:global(.dark) .mm-export-options {
  border-bottom-color: #44403c;
}

.mm-export-options__row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mm-export-options__label {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--swiss-muted, #78716c);
}

:global(.dark) .mm-export-options__label {
  color: #a8a29e;
}
</style>
