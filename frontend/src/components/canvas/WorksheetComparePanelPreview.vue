<script setup lang="ts">
/**
 * One compare slot in the worksheet paper preview — same drag / resize / crop as single.
 */
import { computed, watch } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import {
  DIAGRAM_CROP_EDGES,
  useWorksheetDiagramPreviewDrag,
} from '@/composables/canvas/useWorksheetDiagramPreviewDrag'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  previewUrl: string | null
  loading?: boolean
  label: string
  offsetX: number
  offsetY: number
  scale: number
  cropTop: number
  cropRight: number
  cropBottom: number
  cropLeft: number
}>()

const emit = defineEmits<{
  'update:offsetX': [value: number]
  'update:offsetY': [value: number]
  'update:scale': [value: number]
  'update:cropTop': [value: number]
  'update:cropRight': [value: number]
  'update:cropBottom': [value: number]
  'update:cropLeft': [value: number]
}>()

const { t } = useLanguage()

const offsetX = computed({
  get: () => props.offsetX,
  set: (value: number) => emit('update:offsetX', value),
})
const offsetY = computed({
  get: () => props.offsetY,
  set: (value: number) => emit('update:offsetY', value),
})
const scale = computed({
  get: () => props.scale,
  set: (value: number) => emit('update:scale', value),
})
const cropTop = computed({
  get: () => props.cropTop,
  set: (value: number) => emit('update:cropTop', value),
})
const cropRight = computed({
  get: () => props.cropRight,
  set: (value: number) => emit('update:cropRight', value),
})
const cropBottom = computed({
  get: () => props.cropBottom,
  set: (value: number) => emit('update:cropBottom', value),
})
const cropLeft = computed({
  get: () => props.cropLeft,
  set: (value: number) => emit('update:cropLeft', value),
})

const enabled = computed(() => Boolean(props.previewUrl))

const {
  diagramBodyRef,
  diagramImgRef,
  diagramFrameRef,
  dragging,
  resizing,
  croppingAxis,
  showCenterGuideX,
  showCenterGuideY,
  diagramFrameStyle,
  diagramImageStyle,
  onFramePointerDown,
  onFramePointerMove,
  onFramePointerUp,
  onFramePointerCancel,
  onCropKeyDown,
  onDiagramImageLoad,
  syncFreeSpace,
} = useWorksheetDiagramPreviewDrag({
  offsetX,
  offsetY,
  scale,
  cropTop,
  cropRight,
  cropBottom,
  cropLeft,
  enabled,
})

watch(
  () => props.previewUrl,
  () => {
    void syncFreeSpace()
  }
)

function cropValue(field: (typeof DIAGRAM_CROP_EDGES)[number]['field']): number {
  if (field === 'diagramCropTop') return props.cropTop
  if (field === 'diagramCropRight') return props.cropRight
  if (field === 'diagramCropBottom') return props.cropBottom
  return props.cropLeft
}
</script>

<template>
  <div class="worksheet-text-modal__compare-panel">
    <div
      ref="diagramBodyRef"
      class="worksheet-text-modal__paper-diagram-body worksheet-text-modal__compare-panel-body"
      :class="{ 'is-dragging': dragging, 'is-resizing': resizing }"
    >
      <span
        v-if="showCenterGuideX"
        class="worksheet-text-modal__center-guide worksheet-text-modal__center-guide--x"
        aria-hidden="true"
      />
      <span
        v-if="showCenterGuideY"
        class="worksheet-text-modal__center-guide worksheet-text-modal__center-guide--y"
        aria-hidden="true"
      />
      <div
        v-if="previewUrl"
        ref="diagramFrameRef"
        class="worksheet-text-modal__diagram-frame"
        :class="{
          'is-dragging': dragging,
          'is-resizing': resizing,
          'is-cropping-x': croppingAxis === 'x',
          'is-cropping-y': croppingAxis === 'y',
        }"
        :style="diagramFrameStyle"
        @pointerdown="onFramePointerDown"
        @pointermove="onFramePointerMove"
        @pointerup="onFramePointerUp"
        @pointercancel="onFramePointerCancel"
      >
        <div class="worksheet-text-modal__diagram-viewport">
          <img
            ref="diagramImgRef"
            :src="previewUrl"
            class="worksheet-text-modal__paper-diagram-img"
            :style="diagramImageStyle"
            alt=""
            draggable="false"
            @load="onDiagramImageLoad"
          />
        </div>
        <span
          class="worksheet-text-modal__diagram-handle worksheet-text-modal__diagram-handle--nw"
          data-handle="nw"
        />
        <span
          class="worksheet-text-modal__diagram-handle worksheet-text-modal__diagram-handle--ne"
          data-handle="ne"
        />
        <span
          class="worksheet-text-modal__diagram-handle worksheet-text-modal__diagram-handle--sw"
          data-handle="sw"
        />
        <span
          class="worksheet-text-modal__diagram-handle worksheet-text-modal__diagram-handle--se"
          data-handle="se"
        />
        <span
          v-for="edge in DIAGRAM_CROP_EDGES"
          :key="edge.id"
          class="worksheet-text-modal__diagram-crop"
          :class="`worksheet-text-modal__diagram-crop--${edge.id}`"
          :data-handle="edge.id"
          :aria-label="t(edge.labelKey)"
          role="slider"
          :aria-valuemin="0"
          :aria-valuemax="75"
          :aria-valuenow="Math.round(cropValue(edge.field) * 100)"
          :aria-orientation="edge.id === 'n' || edge.id === 's' ? 'vertical' : 'horizontal'"
          tabindex="0"
          @keydown="onCropKeyDown($event, edge.id)"
        />
      </div>
      <p
        v-else-if="loading"
        class="worksheet-text-modal__paper-diagram-status"
      >
        <I18nText k="canvas.worksheetText.previewLoading" />
      </p>
    </div>
    <p class="worksheet-text-modal__compare-label">
      {{ label }}
    </p>
  </div>
</template>
