<script setup lang="ts">
/**
 * Worksheet header settings — classroom print fields (name, class, date, instructions).
 * Wide Swiss stone shell with live paper preview of the real diagram.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { ElButton, ElDialog, ElInput } from 'element-plus'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useWorksheetDiagramPreviewDrag } from '@/composables/canvas/useWorksheetDiagramPreviewDrag'
import { useLanguage } from '@/composables/core/useLanguage'
import type {
  CanvasExportColorMode,
  CanvasExportLayout,
} from '@/config/canvasExportOptions'
import {
  CLASSROOM_WORKSHEET_TEXT_PRESET,
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  hasActiveWorksheetHeader,
  resolveWorksheetTopicText,
  type CanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'

import '@/styles/canvas-worksheet-text-modal.css'

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    options: CanvasWorksheetTextOptions
    colorMode?: CanvasExportColorMode
    layout?: CanvasExportLayout
    defaultTopic?: string
    captureDiagramPreview?: (preview?: {
      colorMode?: CanvasExportColorMode
    }) => Promise<string | null>
  }>(),
  {
    colorMode: 'color',
    layout: 'landscape',
    defaultTopic: '',
    captureDiagramPreview: undefined,
  }
)

const emit = defineEmits<{
  save: [payload: {
    worksheetText: CanvasWorksheetTextOptions
    colorMode: CanvasExportColorMode
    layout: CanvasExportLayout
    format: 'pdf' | 'worksheet_docx'
  }]
}>()

const { t } = useLanguage()

const draft = ref<CanvasWorksheetTextOptions>({ ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS })
const draftColorMode = ref<CanvasExportColorMode>('color')
const draftLayout = ref<CanvasExportLayout>('landscape')
const diagramPreviewUrl = ref<string | null>(null)
const previewLoading = ref(false)
const previewFailed = ref(false)
let previewRequestId = 0

const previewTopic = computed(() =>
  resolveWorksheetTopicText(draft.value, props.defaultTopic)
)

const previewHasHeader = computed(() => hasActiveWorksheetHeader(draft.value))

const previewInstruction = computed(() => {
  const custom = draft.value.instructionText.trim()
  return custom || t('canvas.worksheetText.defaultInstruction')
})

const showHideOptions = computed(() => [
  { label: t('canvas.worksheetText.show'), value: 'show' as const },
  { label: t('canvas.worksheetText.hide'), value: 'hide' as const },
])

const colorOptions = computed(() => [
  { label: t('canvas.exportOptions.colorWireframe'), value: 'wireframe' as const },
  { label: t('canvas.exportOptions.colorColored'), value: 'color' as const },
])

const layoutOptions = computed(() => [
  { label: t('canvas.exportOptions.layoutLandscape'), value: 'landscape' as const },
  { label: t('canvas.exportOptions.layoutPortrait'), value: 'portrait' as const },
])

type WorksheetVisibility = 'show' | 'hide'

function worksheetVisibility(field: keyof Pick<
  CanvasWorksheetTextOptions,
  'showTopic' | 'showName' | 'showClass' | 'showDate' | 'showInstruction'
>) {
  return computed({
    get: (): WorksheetVisibility => (draft.value[field] ? 'show' : 'hide'),
    set: (value: WorksheetVisibility) => {
      draft.value[field] = value === 'show'
    },
  })
}

const showTopicVisibility = worksheetVisibility('showTopic')
const showNameVisibility = worksheetVisibility('showName')
const showClassVisibility = worksheetVisibility('showClass')
const showDateVisibility = worksheetVisibility('showDate')
const showInstructionVisibility = worksheetVisibility('showInstruction')

const diagramOffsetX = computed({
  get: () => draft.value.diagramOffsetX,
  set: (value: number) => {
    draft.value.diagramOffsetX = value
  },
})
const diagramOffsetY = computed({
  get: () => draft.value.diagramOffsetY,
  set: (value: number) => {
    draft.value.diagramOffsetY = value
  },
})
const diagramScale = computed({
  get: () => draft.value.diagramScale,
  set: (value: number) => {
    draft.value.diagramScale = value
  },
})
const diagramDragEnabled = computed(() => Boolean(diagramPreviewUrl.value))

const {
  diagramBodyRef,
  diagramImgRef,
  diagramFrameRef,
  dragging,
  resizing,
  showCenterGuideX,
  showCenterGuideY,
  diagramFrameStyle,
  onFramePointerDown,
  onFramePointerMove,
  onFramePointerUp,
  onFramePointerCancel,
  onDiagramImageLoad,
  syncFreeSpace,
  resetInteraction,
} = useWorksheetDiagramPreviewDrag({
  offsetX: diagramOffsetX,
  offsetY: diagramOffsetY,
  scale: diagramScale,
  enabled: diagramDragEnabled,
})

function seedDraftFromProps() {
  // Keep empty topicText so export falls back to the live diagram title.
  draft.value = {
    ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
    ...props.options,
  }
  draftColorMode.value = props.colorMode
  draftLayout.value = props.layout
}

function clearPreviewState() {
  previewRequestId += 1
  previewLoading.value = false
  previewFailed.value = false
  diagramPreviewUrl.value = null
  resetInteraction()
}

async function refreshDiagramPreview() {
  if (!props.captureDiagramPreview) {
    previewFailed.value = true
    diagramPreviewUrl.value = null
    return
  }
  const requestId = ++previewRequestId
  previewLoading.value = true
  previewFailed.value = false
  try {
    const dataUrl = await props.captureDiagramPreview({
      colorMode: draftColorMode.value,
    })
    if (requestId !== previewRequestId) return
    if (dataUrl) {
      diagramPreviewUrl.value = dataUrl
      previewFailed.value = false
      await nextTick()
      syncFreeSpace()
      return
    }
    // Busy export / empty capture: keep prior preview if we have one.
    if (!diagramPreviewUrl.value) {
      previewFailed.value = true
    }
  } catch {
    if (requestId !== previewRequestId) return
    diagramPreviewUrl.value = null
    previewFailed.value = true
  } finally {
    if (requestId === previewRequestId) {
      previewLoading.value = false
    }
  }
}

watch(
  () => props.options,
  () => {
    if (visible.value) {
      seedDraftFromProps()
    }
  },
  { deep: true }
)

watch(
  () => visible.value,
  (open) => {
    if (!open) {
      clearPreviewState()
      return
    }
    seedDraftFromProps()
    void refreshDiagramPreview()
  }
)

watch(draftColorMode, () => {
  if (visible.value) {
    void refreshDiagramPreview()
  }
})

watch(draftLayout, async () => {
  if (!visible.value) return
  await nextTick()
  syncFreeSpace()
})

function close() {
  visible.value = false
}

function commitExport(format: 'pdf' | 'worksheet_docx') {
  const worksheetText = { ...draft.value }
  const liveTopic = props.defaultTopic.trim()
  // Don't freeze the current title into sessionStorage when user didn't override it.
  if (liveTopic && worksheetText.topicText.trim() === liveTopic) {
    worksheetText.topicText = ''
  }
  emit('save', {
    worksheetText,
    colorMode: draftColorMode.value,
    layout: draftLayout.value,
    format,
  })
  visible.value = false
}

function handleExportPdf() {
  commitExport('pdf')
}

function handleExportDocx() {
  commitExport('worksheet_docx')
}

async function handleReset() {
  // Full factory defaults: fields, placement, scale, color mode, and paper orientation.
  draft.value = { ...CLASSROOM_WORKSHEET_TEXT_PRESET }
  draftColorMode.value = 'color'
  draftLayout.value = 'landscape'
  await nextTick()
  syncFreeSpace()
}
</script>

<template>
  <ElDialog
    v-model="visible"
    width="920px"
    append-to-body
    destroy-on-close
    align-center
    class="worksheet-text-modal"
    :show-close="true"
    @close="close"
  >
    <template #header>
      <div class="worksheet-text-modal__header">
        <span
          class="worksheet-text-modal__glyph"
          aria-hidden="true"
        >◇</span>
        <h2 class="worksheet-text-modal__title">
          {{ t('canvas.worksheetText.modalTitle') }}
        </h2>
        <span
          class="worksheet-text-modal__header-rule"
          aria-hidden="true"
        />
        <span class="worksheet-text-modal__header-note">
          {{ t('canvas.worksheetText.previewLabel') }}
        </span>
      </div>
    </template>

    <div class="worksheet-text-modal__layout">
      <aside
        class="worksheet-text-modal__preview-pane"
        :aria-label="t('canvas.worksheetText.previewLabel')"
      >
        <div class="worksheet-text-modal__preview-kicker">
          <span>{{ t('canvas.worksheetText.previewLabel') }}</span>
          <span class="worksheet-text-modal__preview-kicker-meta">
            A4 ·
            {{
              draftLayout === 'portrait'
                ? t('canvas.exportOptions.layoutPortrait')
                : t('canvas.exportOptions.layoutLandscape')
            }}
          </span>
        </div>
        <div class="worksheet-text-modal__paper-stage">
          <div
            class="worksheet-text-modal__paper"
            :class="`worksheet-text-modal__paper--${draftLayout}`"
          >
            <div
              v-if="previewHasHeader"
              class="worksheet-text-modal__paper-header"
            >
              <p
                v-if="draft.showTopic && previewTopic"
                class="worksheet-text-modal__paper-topic"
              >
                {{ previewTopic }}
              </p>
              <div
                v-if="draft.showName || draft.showClass || draft.showDate"
                class="worksheet-text-modal__paper-meta"
              >
                <span
                  v-if="draft.showName"
                  class="worksheet-text-modal__paper-field"
                >
                  <span>{{ t('canvas.worksheetText.fieldName') }}</span>
                  <span
                    class="worksheet-text-modal__paper-line"
                    aria-hidden="true"
                  />
                </span>
                <span
                  v-if="draft.showClass"
                  class="worksheet-text-modal__paper-field"
                >
                  <span>{{ t('canvas.worksheetText.fieldClass') }}</span>
                  <span
                    class="worksheet-text-modal__paper-line worksheet-text-modal__paper-line--short"
                    aria-hidden="true"
                  />
                </span>
                <span
                  v-if="draft.showDate"
                  class="worksheet-text-modal__paper-field"
                >
                  <span>{{ t('canvas.worksheetText.fieldDate') }}</span>
                  <span
                    class="worksheet-text-modal__paper-line"
                    aria-hidden="true"
                  />
                </span>
              </div>
              <p
                v-if="draft.showInstruction"
                class="worksheet-text-modal__paper-instruction"
              >
                {{ t('canvas.worksheetText.instructionPrefix') }}{{ previewInstruction }}
              </p>
            </div>
            <div
              v-else
              class="worksheet-text-modal__paper-empty"
            >
              {{ t('canvas.worksheetText.previewEmpty') }}
            </div>
            <div class="worksheet-text-modal__paper-diagram">
              <div
                ref="diagramBodyRef"
                class="worksheet-text-modal__paper-diagram-body"
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
                  v-if="diagramPreviewUrl"
                  ref="diagramFrameRef"
                  class="worksheet-text-modal__diagram-frame"
                  :class="{ 'is-dragging': dragging, 'is-resizing': resizing }"
                  :style="diagramFrameStyle"
                  @pointerdown="onFramePointerDown"
                  @pointermove="onFramePointerMove"
                  @pointerup="onFramePointerUp"
                  @pointercancel="onFramePointerCancel"
                >
                  <img
                    ref="diagramImgRef"
                    :src="diagramPreviewUrl"
                    class="worksheet-text-modal__paper-diagram-img"
                    alt=""
                    draggable="false"
                    @load="onDiagramImageLoad"
                  >
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
                </div>
                <p
                  v-else-if="previewLoading"
                  class="worksheet-text-modal__paper-diagram-status"
                >
                  {{ t('canvas.worksheetText.previewLoading') }}
                </p>
                <p
                  v-else-if="previewFailed"
                  class="worksheet-text-modal__paper-diagram-status"
                >
                  {{ t('canvas.worksheetText.previewFailed') }}
                </p>
              </div>
              <p
                v-if="diagramPreviewUrl"
                class="worksheet-text-modal__paper-diagram-hint"
              >
                {{ t('canvas.worksheetText.dragDiagramHint') }}
              </p>
            </div>
          </div>
        </div>
      </aside>

      <div class="worksheet-text-modal__controls">
        <div class="worksheet-text-modal__fields">
          <div class="worksheet-text-modal__row">
            <span class="worksheet-text-modal__label">{{
              t('canvas.worksheetText.showTopic')
            }}</span>
            <AdminSwissSegmented
              v-model="showTopicVisibility"
              fit
              :options="showHideOptions"
              :aria-label="t('canvas.worksheetText.showTopic')"
            />
          </div>

          <div class="worksheet-text-modal__field-input">
            <span class="worksheet-text-modal__kicker">{{
              t('canvas.worksheetText.topicPreviewLabel')
            }}</span>
            <ElInput
              v-model="draft.topicText"
              :placeholder="defaultTopic || t('canvas.worksheetText.topicPreviewLabel')"
              class="worksheet-text-modal__input"
            />
          </div>

          <div class="worksheet-text-modal__row">
            <span class="worksheet-text-modal__label">{{
              t('canvas.worksheetText.showName')
            }}</span>
            <AdminSwissSegmented
              v-model="showNameVisibility"
              fit
              :options="showHideOptions"
              :aria-label="t('canvas.worksheetText.showName')"
            />
          </div>

          <div class="worksheet-text-modal__row">
            <span class="worksheet-text-modal__label">{{
              t('canvas.worksheetText.showClass')
            }}</span>
            <AdminSwissSegmented
              v-model="showClassVisibility"
              fit
              :options="showHideOptions"
              :aria-label="t('canvas.worksheetText.showClass')"
            />
          </div>

          <div class="worksheet-text-modal__row">
            <span class="worksheet-text-modal__label">{{
              t('canvas.worksheetText.showDate')
            }}</span>
            <AdminSwissSegmented
              v-model="showDateVisibility"
              fit
              :options="showHideOptions"
              :aria-label="t('canvas.worksheetText.showDate')"
            />
          </div>

          <div class="worksheet-text-modal__row">
            <span class="worksheet-text-modal__label">{{
              t('canvas.worksheetText.showInstruction')
            }}</span>
            <AdminSwissSegmented
              v-model="showInstructionVisibility"
              fit
              :options="showHideOptions"
              :aria-label="t('canvas.worksheetText.showInstruction')"
            />
          </div>
        </div>

        <div
          v-if="draft.showInstruction"
          class="worksheet-text-modal__instruction"
        >
          <span class="worksheet-text-modal__kicker">{{
            t('canvas.worksheetText.instructionLabel')
          }}</span>
          <ElInput
            v-model="draft.instructionText"
            type="textarea"
            :rows="3"
            :placeholder="t('canvas.worksheetText.defaultInstruction')"
            class="worksheet-text-modal__textarea"
          />
        </div>

        <div class="worksheet-text-modal__row">
          <span class="worksheet-text-modal__label">{{
            t('canvas.exportOptions.colorLabel')
          }}</span>
          <AdminSwissSegmented
            v-model="draftColorMode"
            fit
            :options="colorOptions"
            :aria-label="t('canvas.exportOptions.colorLabel')"
          />
        </div>

        <div class="worksheet-text-modal__row">
          <span class="worksheet-text-modal__label">{{
            t('canvas.exportOptions.layoutLabel')
          }}</span>
          <AdminSwissSegmented
            v-model="draftLayout"
            fit
            :options="layoutOptions"
            :aria-label="t('canvas.exportOptions.layoutLabel')"
          />
        </div>

        <p class="worksheet-text-modal__hint">{{ t('canvas.worksheetText.modalHint') }}</p>
      </div>
    </div>

    <template #footer>
      <div class="worksheet-text-modal__footer">
        <ElButton
          class="worksheet-text-modal__btn"
          @click="handleReset"
        >
          {{ t('canvas.worksheetText.reset') }}
        </ElButton>
        <div class="worksheet-text-modal__footer-actions">
          <ElButton
            class="worksheet-text-modal__btn"
            @click="close"
          >
            {{ t('canvas.worksheetText.cancel') }}
          </ElButton>
          <ElButton
            class="worksheet-text-modal__btn"
            @click="handleExportDocx"
          >
            {{ t('canvas.worksheetText.exportDocx') }}
          </ElButton>
          <ElButton
            type="primary"
            class="worksheet-text-modal__btn worksheet-text-modal__btn--primary"
            @click="handleExportPdf"
          >
            {{ t('canvas.worksheetText.exportPdf') }}
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>
