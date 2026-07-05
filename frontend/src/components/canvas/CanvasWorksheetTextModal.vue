<script setup lang="ts">
/**
 * Worksheet header settings — classroom print fields (name, class, date, instructions).
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElDialog, ElInput } from 'element-plus'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  CLASSROOM_WORKSHEET_TEXT_PRESET,
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  type CanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import { useDiagramStore } from '@/stores'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  options: CanvasWorksheetTextOptions
}>()

const emit = defineEmits<{
  save: [options: CanvasWorksheetTextOptions]
}>()

const { t, currentLanguage } = useLanguage()
const diagramStore = useDiagramStore()

const draft = ref<CanvasWorksheetTextOptions>({ ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS })

const topicPreview = computed(() =>
  resolveDiagramTitleForSave(
    diagramStore.effectiveTitle,
    diagramStore.type,
    currentLanguage.value
  )
)

const showHideOptions = computed(() => [
  { label: t('canvas.worksheetText.show'), value: 'show' as const },
  { label: t('canvas.worksheetText.hide'), value: 'hide' as const },
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

watch(
  () => props.options,
  (value) => {
    draft.value = { ...value }
  },
  { immediate: true, deep: true }
)

watch(
  () => visible.value,
  (open) => {
    if (open) {
      draft.value = { ...props.options }
    }
  }
)

function close() {
  visible.value = false
}

function handleSave() {
  emit('save', { ...draft.value })
  visible.value = false
}

function handleReset() {
  draft.value = { ...CLASSROOM_WORKSHEET_TEXT_PRESET }
}
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="t('canvas.worksheetText.modalTitle')"
    width="520px"
    append-to-body
    destroy-on-close
    class="worksheet-text-modal"
    @close="close"
  >
    <div class="worksheet-text-modal__body">
      <div class="worksheet-text-modal__topic-block">
        <span class="worksheet-text-modal__topic-label">{{
          t('canvas.worksheetText.topicPreviewLabel')
        }}</span>
        <p class="worksheet-text-modal__topic-value">{{ topicPreview }}</p>
      </div>

      <div class="worksheet-text-modal__row">
        <span class="worksheet-text-modal__label">{{ t('canvas.worksheetText.showTopic') }}</span>
        <AdminSwissSegmented
          v-model="showTopicVisibility"
          fit
          :options="showHideOptions"
          :aria-label="t('canvas.worksheetText.showTopic')"
        />
      </div>

      <div class="worksheet-text-modal__row">
        <span class="worksheet-text-modal__label">{{ t('canvas.worksheetText.showName') }}</span>
        <AdminSwissSegmented
          v-model="showNameVisibility"
          fit
          :options="showHideOptions"
          :aria-label="t('canvas.worksheetText.showName')"
        />
      </div>

      <div class="worksheet-text-modal__row">
        <span class="worksheet-text-modal__label">{{ t('canvas.worksheetText.showClass') }}</span>
        <AdminSwissSegmented
          v-model="showClassVisibility"
          fit
          :options="showHideOptions"
          :aria-label="t('canvas.worksheetText.showClass')"
        />
      </div>

      <div class="worksheet-text-modal__row">
        <span class="worksheet-text-modal__label">{{ t('canvas.worksheetText.showDate') }}</span>
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

      <div
        v-if="draft.showInstruction"
        class="worksheet-text-modal__instruction"
      >
        <span class="worksheet-text-modal__label">{{
          t('canvas.worksheetText.instructionLabel')
        }}</span>
        <ElInput
          v-model="draft.instructionText"
          type="textarea"
          :rows="2"
          :placeholder="t('canvas.worksheetText.defaultInstruction')"
        />
      </div>

      <p class="worksheet-text-modal__hint">{{ t('canvas.worksheetText.modalHint') }}</p>
    </div>

    <template #footer>
      <div class="worksheet-text-modal__footer">
        <ElButton @click="handleReset">{{ t('canvas.worksheetText.reset') }}</ElButton>
        <div class="worksheet-text-modal__footer-actions">
          <ElButton @click="close">{{ t('canvas.worksheetText.cancel') }}</ElButton>
          <ElButton
            type="primary"
            @click="handleSave"
          >
            {{ t('canvas.worksheetText.save') }}
          </ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.worksheet-text-modal__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.worksheet-text-modal__topic-block {
  padding: 10px 12px;
  border: 1px solid var(--swiss-border, #e7e5e4);
  border-radius: 8px;
  background: var(--swiss-surface-muted, #fafaf9);
}

:global(.dark) .worksheet-text-modal__topic-block {
  border-color: #44403c;
  background: #292524;
}

.worksheet-text-modal__topic-label {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--swiss-muted, #78716c);
}

.worksheet-text-modal__topic-value {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
  color: #1c1917;
}

:global(.dark) .worksheet-text-modal__topic-value {
  color: #fafaf9;
}

.worksheet-text-modal__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.worksheet-text-modal__label {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
}

:global(.dark) .worksheet-text-modal__label {
  color: #d6d3d1;
}

.worksheet-text-modal__instruction {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.worksheet-text-modal__hint {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--swiss-muted, #78716c);
}

.worksheet-text-modal__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}

.worksheet-text-modal__footer-actions {
  display: flex;
  gap: 8px;
}
</style>
