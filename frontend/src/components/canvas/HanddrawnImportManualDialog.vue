<script setup lang="ts">
/**
 * Manual confirm for 图片/手绘图.
 * The vision result stays here until the user checks the type and the text.
 */
import { computed } from 'vue'

import { ElButton, ElDialog, ElInput, ElOption, ElSelect } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  type HanddrawnManualDraft,
  VISION_IMPORT_TYPES,
  isVisionImportType,
  manualFormKind,
  retargetDraft,
} from '@/utils/handdrawnImportManual'

const draft = defineModel<HanddrawnManualDraft | null>('draft', { required: true })

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const { t } = useLanguage()

const visible = computed({
  get: () => draft.value !== null,
  set: (open: boolean) => {
    if (!open) emit('cancel')
  },
})

const kind = computed(() => (draft.value ? manualFormKind(draft.value.diagramType) : 'list'))

const topicLabelKey = computed(() => {
  const type = draft.value?.diagramType
  if (type === 'brace_map') return 'canvas.toolbar.importHanddrawnFieldWhole'
  if (type === 'multi_flow_map') return 'canvas.toolbar.importHanddrawnFieldEvent'
  if (type === 'flow_map') return 'canvas.toolbar.importHanddrawnFieldTitle'
  return 'canvas.toolbar.importHanddrawnFieldTopic'
})

const itemsLabelKey = computed(() => {
  const type = draft.value?.diagramType
  if (type === 'bubble_map') return 'canvas.toolbar.importHanddrawnFieldAttributes'
  if (type === 'circle_map') return 'canvas.toolbar.importHanddrawnFieldContext'
  if (type === 'concept_map') return 'canvas.toolbar.importHanddrawnFieldConcepts'
  if (type === 'multi_flow_map') return 'canvas.toolbar.importHanddrawnFieldCauses'
  return 'canvas.toolbar.importHanddrawnFieldItems'
})

function onTypeChange(next: unknown): void {
  if (typeof next !== 'string') return
  if (!draft.value || !isVisionImportType(next) || draft.value.diagramType === next) return
  draft.value = retargetDraft(draft.value, next)
}

function addStep(): void {
  draft.value?.steps.push({ text: '', substeps: '' })
}

function removeStep(index: number): void {
  if (!draft.value) return
  draft.value.steps.splice(index, 1)
  if (draft.value.steps.length === 0) {
    draft.value.steps.push({ text: '', substeps: '' })
  }
}
</script>

<template>
  <ElDialog
    v-model="visible"
    width="560px"
    append-to-body
    class="handdrawn-manual"
    :title="t('canvas.toolbar.importHanddrawnManualTitle')"
  >
    <div
      v-if="draft"
      class="handdrawn-manual__body"
    >
      <p class="handdrawn-manual__hint">
        <I18nText k="canvas.toolbar.importHanddrawnManualHint" />
      </p>
      <label class="handdrawn-manual__field">
        <span><I18nText k="canvas.toolbar.importHanddrawnManualType" /></span>
        <ElSelect
          :model-value="draft.diagramType"
          @update:model-value="onTypeChange"
        >
          <ElOption
            v-for="diagramType in VISION_IMPORT_TYPES"
            :key="diagramType"
            :label="t(`sidebar.diagramType.${diagramType}`)"
            :value="diagramType"
          >
            <I18nText :k="`sidebar.diagramType.${diagramType}`" />
          </ElOption>
        </ElSelect>
      </label>

      <label
        v-if="kind !== 'bridge'"
        class="handdrawn-manual__field"
      >
        <span><I18nText :k="topicLabelKey" /></span>
        <ElInput v-model="draft.topic" />
      </label>

      <label
        v-if="kind === 'list' || kind === 'concept' || kind === 'multi'"
        class="handdrawn-manual__field"
      >
        <span><I18nText :k="itemsLabelKey" /></span>
        <ElInput
          v-model="draft.items"
          type="textarea"
          :rows="kind === 'multi' ? 4 : 8"
        />
      </label>

      <template v-if="kind === 'double'">
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldRight" /></span>
          <ElInput v-model="draft.right" />
        </label>
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldSimilarities" /></span>
          <ElInput
            v-model="draft.similarities"
            type="textarea"
            :rows="4"
          />
        </label>
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldLeftDiff" /></span>
          <ElInput
            v-model="draft.leftDifferences"
            type="textarea"
            :rows="4"
          />
        </label>
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldRightDiff" /></span>
          <ElInput
            v-model="draft.rightDifferences"
            type="textarea"
            :rows="4"
          />
        </label>
      </template>

      <template v-if="kind === 'multi'">
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldEffects" /></span>
          <ElInput
            v-model="draft.effects"
            type="textarea"
            :rows="4"
          />
        </label>
      </template>

      <template v-if="kind === 'outline'">
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldOutline" /></span>
          <ElInput
            v-model="draft.outline"
            type="textarea"
            :rows="12"
          />
        </label>
        <p class="handdrawn-manual__note">
          <I18nText k="canvas.toolbar.importHanddrawnOutlineHint" />
        </p>
      </template>

      <template v-if="kind === 'flow'">
        <div
          v-for="(step, index) in draft.steps"
          :key="index"
          class="handdrawn-manual__step"
        >
          <label class="handdrawn-manual__field">
            <span>
              <I18nText k="canvas.toolbar.importHanddrawnFieldStep" />
              {{ index + 1 }}
            </span>
            <ElInput v-model="step.text" />
          </label>
          <label class="handdrawn-manual__field">
            <span><I18nText k="canvas.toolbar.importHanddrawnFieldSubsteps" /></span>
            <ElInput
              v-model="step.substeps"
              type="textarea"
              :rows="3"
            />
          </label>
          <button
            type="button"
            class="handdrawn-manual__text-btn"
            @click="removeStep(index)"
          >
            <I18nText k="canvas.toolbar.importHanddrawnRemoveStep" />
          </button>
        </div>
        <button
          type="button"
          class="handdrawn-manual__text-btn"
          @click="addStep"
        >
          <I18nText k="canvas.toolbar.importHanddrawnAddStep" />
        </button>
      </template>

      <template v-if="kind === 'bridge'">
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldRelating" /></span>
          <ElInput v-model="draft.relating" />
        </label>
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldPairs" /></span>
          <ElInput
            v-model="draft.pairs"
            type="textarea"
            :rows="8"
          />
        </label>
        <p class="handdrawn-manual__note">
          <I18nText k="canvas.toolbar.importHanddrawnPairsHint" />
        </p>
      </template>

      <template v-if="kind === 'concept'">
        <label class="handdrawn-manual__field">
          <span><I18nText k="canvas.toolbar.importHanddrawnFieldRelationships" /></span>
          <ElInput
            v-model="draft.relationships"
            type="textarea"
            :rows="6"
          />
        </label>
        <p class="handdrawn-manual__note">
          <I18nText k="canvas.toolbar.importHanddrawnRelationshipsHint" />
        </p>
      </template>
    </div>
    <template #footer>
      <ElButton @click="emit('cancel')">
        <I18nText k="canvas.toolbar.importHanddrawnManualCancel" />
      </ElButton>
      <ElButton
        type="primary"
        @click="emit('confirm')"
      >
        <I18nText k="canvas.toolbar.importHanddrawnManualImport" />
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.handdrawn-manual__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 62vh;
  overflow: auto;
}

.handdrawn-manual__hint,
.handdrawn-manual__note {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.handdrawn-manual__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.handdrawn-manual__step {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.handdrawn-manual__text-btn {
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 13px;
}
</style>
