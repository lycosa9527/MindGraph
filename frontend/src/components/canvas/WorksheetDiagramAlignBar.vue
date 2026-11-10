<script setup lang="ts">
/**
 * Left / center / right placement for the worksheet diagram preview.
 */
import { AlignCenter, AlignLeft, AlignRight } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import type { WorksheetDiagramAlign } from '@/composables/canvas/useWorksheetDiagramPreviewDrag'
import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  align: WorksheetDiagramAlign | null
}>()

const emit = defineEmits<{
  align: [value: WorksheetDiagramAlign]
}>()

const { t } = useLanguage()

const actions = [
  { id: 'left', labelKey: 'canvas.worksheetText.alignLeft', icon: AlignLeft },
  { id: 'center', labelKey: 'canvas.worksheetText.centerDiagram', icon: AlignCenter },
  { id: 'right', labelKey: 'canvas.worksheetText.alignRight', icon: AlignRight },
] as const
</script>

<template>
  <div
    class="worksheet-text-modal__align"
    role="group"
    :aria-label="t('canvas.worksheetText.alignGroup')"
  >
    <button
      v-for="item in actions"
      :key="item.id"
      type="button"
      class="worksheet-text-modal__align-btn"
      :aria-pressed="align === item.id"
      :aria-label="t(item.labelKey)"
      @click="emit('align', item.id)"
    >
      <component
        :is="item.icon"
        class="worksheet-text-modal__align-icon"
        :size="14"
        aria-hidden="true"
      />
      <I18nText :k="item.labelKey" />
    </button>
  </div>
</template>
