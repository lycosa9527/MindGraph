<script setup lang="ts">
/**
 * Left / center / right placement for the worksheet diagram preview.
 */
import { AlignCenter, AlignLeft, AlignRight, QrCode } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import type { WorksheetDiagramAlign } from '@/composables/canvas/useWorksheetDiagramPreviewDrag'
import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  align: WorksheetDiagramAlign | null
  qrOn: boolean
  qrBusy: boolean
  classOn: boolean
  classBusy: boolean
  classes: { id: number; name: string }[]
  classId: number | null
}>()

const emit = defineEmits<{
  align: [value: WorksheetDiagramAlign]
  toggleQr: []
  toggleClass: []
  selectClass: [classId: number]
}>()

const { t } = useLanguage()

function onClassChange(event: Event): void {
  const value = Number((event.target as HTMLSelectElement).value)
  if (value > 0) emit('selectClass', value)
}

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
    <button
      type="button"
      class="worksheet-text-modal__align-btn worksheet-text-modal__align-btn--qr"
      :aria-pressed="qrOn"
      :aria-label="t('canvas.worksheetText.sheetQrHint')"
      :title="t('canvas.worksheetText.sheetQrHint')"
      :disabled="qrBusy"
      @click="emit('toggleQr')"
    >
      <QrCode
        class="worksheet-text-modal__align-icon"
        :size="14"
        aria-hidden="true"
      />
      <I18nText k="canvas.worksheetText.sheetQr" />
    </button>
    <button
      type="button"
      class="worksheet-text-modal__align-btn worksheet-text-modal__align-btn--qr"
      :aria-pressed="classOn"
      :aria-label="t('canvas.worksheetText.classPersonalHint')"
      :title="t('canvas.worksheetText.classPersonalHint')"
      :disabled="classBusy || qrBusy"
      @click="emit('toggleClass')"
    >
      <I18nText k="canvas.worksheetText.classPersonal" />
    </button>
    <select
      v-if="classOn && classes.length > 1"
      class="worksheet-text-modal__class-select"
      :value="classId ?? ''"
      :disabled="classBusy"
      @change="onClassChange"
    >
      <option
        v-for="item in classes"
        :key="item.id"
        :value="item.id"
      >
        {{ item.name }}
      </option>
    </select>
  </div>
</template>
