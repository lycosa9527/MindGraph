<script setup lang="ts">
/**
 * Split「AI生成图示」control: primary generates; caret opens vertical 学段 seg control.
 */
import { computed, ref } from 'vue'

import { ElPopover, ElTooltip } from 'element-plus'

import { ChevronDown, Wand2 } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { EDUCATION_STAGES, type EducationStage } from '@/constants/educationStage'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(
  defineProps<{
    compact?: boolean
    isAIGenerating: boolean
    aiGenerateLabel: string
    aiGeneratingLabel: string
    /** classic = non–mind-map toolbar; mindmap = mm-btn chrome */
    variant?: 'classic' | 'mindmap'
  }>(),
  { compact: false, variant: 'classic' }
)

const emit = defineEmits<{
  aiGenerate: []
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const popoverVisible = ref(false)
const saving = ref(false)

const selectedStage = computed(() => authStore.getEffectiveEducationStage())
const caretDisabled = computed(() => props.isAIGenerating || saving.value)

const stageLabelKey: Record<EducationStage, string> = {
  小学: 'canvas.toolbar.educationStagePrimary',
  初中: 'canvas.toolbar.educationStageMiddle',
  高中: 'canvas.toolbar.educationStageHigh',
  大学: 'canvas.toolbar.educationStageUniversity',
  成人: 'canvas.toolbar.educationStageAdult',
  专家: 'canvas.toolbar.educationStageExpert',
}

async function selectStage(stage: EducationStage): Promise<void> {
  const next = selectedStage.value === stage ? null : stage
  saving.value = true
  await authStore.saveDiagramPreferences(next)
  saving.value = false
  popoverVisible.value = false
}

async function clearStage(): Promise<void> {
  if (selectedStage.value == null) {
    return
  }
  saving.value = true
  await authStore.saveDiagramPreferences(null)
  saving.value = false
  popoverVisible.value = false
}

function onPrimaryClick(): void {
  emit('aiGenerate')
}
</script>

<template>
  <div
    class="ai-split"
    :class="[
      `ai-split--${props.variant}`,
      { 'ai-split--generating': props.isAIGenerating, 'ai-split--compact': props.compact },
    ]"
  >
    <ElTooltip
      :content="
        props.isAIGenerating ? props.aiGeneratingLabel : t('canvas.toolbar.aiGenerateTooltip')
      "
      placement="bottom"
      :disabled="!props.compact"
    >
      <button
        type="button"
        class="ai-split__primary"
        :disabled="props.isAIGenerating"
        :aria-label="props.isAIGenerating ? props.aiGeneratingLabel : props.aiGenerateLabel"
        @click="onPrimaryClick"
      >
        <Wand2
          class="ai-split__icon h-4 w-4 shrink-0"
          aria-hidden="true"
        />
        <span
          v-if="!props.compact"
          class="ai-split__label"
          >{{ props.isAIGenerating ? props.aiGeneratingLabel : props.aiGenerateLabel }}</span
        >
      </button>
    </ElTooltip>

    <ElPopover
      v-model:visible="popoverVisible"
      placement="bottom-end"
      trigger="click"
      :width="140"
      :disabled="caretDisabled"
      :teleported="true"
      popper-class="ai-stage-popper"
      :show-arrow="false"
    >
      <template #reference>
        <!--
          Do not wrap this reference in ElTooltip: nested tooltip steals the
          click target and Element Plus never toggles the popover.
        -->
        <button
          type="button"
          class="ai-split__caret"
          :disabled="caretDisabled"
          :title="t('canvas.toolbar.educationStageTooltip')"
          :aria-label="t('canvas.toolbar.educationStageTooltip')"
          :aria-expanded="popoverVisible"
          :aria-haspopup="true"
        >
          <ChevronDown class="h-3.5 w-3.5 shrink-0" />
        </button>
      </template>

      <div class="ai-stage-panel">
        <div class="ai-stage-panel__title">{{ t('canvas.toolbar.educationStage') }}</div>
        <div
          class="ai-stage-seg"
          role="listbox"
          :aria-label="t('canvas.toolbar.educationStage')"
        >
          <button
            type="button"
            role="option"
            class="ai-stage-seg__item"
            :class="{ 'ai-stage-seg__item--active': selectedStage == null }"
            :aria-selected="selectedStage == null"
            @click="clearStage"
          >
            {{ t('canvas.toolbar.educationStageClear') }}
          </button>
          <button
            v-for="stage in EDUCATION_STAGES"
            :key="stage"
            type="button"
            role="option"
            class="ai-stage-seg__item"
            :class="{ 'ai-stage-seg__item--active': selectedStage === stage }"
            :aria-selected="selectedStage === stage"
            @click="selectStage(stage)"
          >
            {{ t(stageLabelKey[stage]) }}
          </button>
        </div>
      </div>
    </ElPopover>
  </div>
</template>

<style scoped>
.ai-split {
  display: inline-flex;
  align-items: stretch;
  margin-left: 8px;
  border-radius: 6px;
  overflow: hidden;
  vertical-align: middle;
}

.ai-split--mindmap {
  margin-left: 0;
  border-radius: 8px;
  box-shadow:
    0 1px 3px rgb(37 99 235 / 0.35),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
}

.ai-split__primary,
.ai-split__caret {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  color: #fff;
  cursor: pointer;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  transition:
    background 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.ai-split--mindmap .ai-split__primary,
.ai-split--mindmap .ai-split__caret {
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
}

.ai-split__primary {
  padding: 6px 12px 6px 14px;
}

.ai-split--mindmap .ai-split__primary {
  height: 32px;
  padding: 0 10px 0 12px;
  font-size: 13px;
  font-weight: 500;
}

.ai-split--compact .ai-split__primary {
  padding: 6px 10px;
}

.ai-split__caret {
  padding: 0 6px;
  border-left: 1px solid rgb(255 255 255 / 0.28);
  min-width: 26px;
}

.ai-split--mindmap .ai-split__caret {
  min-width: 28px;
}

.ai-split__primary:hover:not(:disabled),
.ai-split__caret:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
}

.ai-split--mindmap .ai-split__primary:hover:not(:disabled),
.ai-split--mindmap .ai-split__caret:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
}

.ai-split__primary:disabled,
.ai-split__caret:disabled {
  cursor: not-allowed;
  opacity: 0.75;
}

.ai-split__label {
  color: #fff;
  white-space: nowrap;
}

.ai-split__icon {
  color: #fff;
}

.ai-stage-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  min-width: 108px;
}

.ai-stage-panel__title {
  margin: 0;
  padding: 2px 0 4px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: #6b7280;
  text-align: center;
}

.ai-stage-seg {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  background: #f8fafc;
}

.ai-stage-seg__item {
  appearance: none;
  border: none;
  border-bottom: 1px solid #e5e7eb;
  background: transparent;
  padding: 9px 14px;
  font-size: 13px;
  line-height: 1.2;
  color: #374151;
  text-align: center;
  cursor: pointer;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.ai-stage-seg__item:last-child {
  border-bottom: none;
}

.ai-stage-seg__item:hover {
  background: #eff6ff;
  color: #1d4ed8;
}

.ai-stage-seg__item--active {
  background: #3b82f6;
  color: #fff;
  font-weight: 600;
}

.ai-stage-seg__item--active:hover {
  background: #2563eb;
  color: #fff;
}
</style>

<style>
.ai-stage-popper.el-popper {
  z-index: 4000 !important;
  padding: 10px !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 12px !important;
  background: #fff !important;
  box-shadow:
    0 8px 24px rgb(15 23 42 / 0.1),
    0 2px 6px rgb(15 23 42 / 0.05) !important;
}

.dark .ai-stage-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
}

.dark .ai-stage-popper .ai-stage-panel__title {
  color: #9ca3af;
}

.dark .ai-stage-popper .ai-stage-seg {
  border-color: #4b5563;
  background: #111827;
}

.dark .ai-stage-popper .ai-stage-seg__item {
  border-bottom-color: #374151;
  color: #e5e7eb;
}

.dark .ai-stage-popper .ai-stage-seg__item:hover {
  background: #1e3a8a;
  color: #bfdbfe;
}
</style>
