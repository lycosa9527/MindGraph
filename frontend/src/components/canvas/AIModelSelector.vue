<script setup lang="ts">
/**
 * AIModelSelector - Bottom center AI model selection and result switching
 *
 * Migrated from old JavaScript llm-progress-renderer.js and llm-autocomplete-manager.js
 *
 * Features:
 * - Shows all 3 AI models: Qwen, DeepSeek, Doubao
 * - Per-model loading/ready/error states with visual feedback
 * - Click ready model to switch to its cached result
 * - Glow effect when result becomes available
 * - Checkmark icon shows currently displayed result
 */
import { computed } from 'vue'

import { ElTooltip } from 'element-plus'

import { Sparkles, X } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { LLM_MODEL_COLORS } from '@/config/llmModelColors'
import {
  useAuthStore,
  useConceptMapFocusReviewStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
} from '@/stores'

const props = withDefaults(
  defineProps<{
    /** Mobile: hide Tab 焦点 badge (e.g. bottom inline-rec strip) */
    hideTabFocusBadge?: boolean
    /** Mobile concept top toolbar: 启用 AI only — hide Tab 焦点 + 关系 badges */
    conceptMapTopToolbar?: boolean
  }>(),
  { hideTabFocusBadge: false, conceptMapTopToolbar: false }
)

const { t } = useLanguage()
const { switchToModel } = useAutoComplete()
const diagramStore = useDiagramStore()
const llmResultsStore = useLLMResultsStore()
const inlineRecStore = useInlineRecommendationsStore()
const authStore = useAuthStore()
const focusReviewStore = useConceptMapFocusReviewStore()
const rootConceptReviewStore = useConceptMapRootConceptReviewStore()

const isConceptMap = computed(() => diagramStore.type === 'concept_map')

/** Concept map: single AI toggle enables relationship-label generation (all models on backend) */
function toggleConceptMapAi(): void {
  if (llmResultsStore.selectedModel) {
    llmResultsStore.setSelectedModel(null)
  } else {
    llmResultsStore.setSelectedModel('qwen')
  }
}

/** Show "关系" when concept map AI is on */
const showRelationshipReady = computed(
  () => isConceptMap.value && llmResultsStore.selectedModel != null
)

/** Tab-style badge when focus topic is long enough to validate (Tab while editing the topic node) */
const showFocusReviewBadge = computed(
  () =>
    isConceptMap.value &&
    !props.conceptMapTopToolbar &&
    !props.hideTabFocusBadge &&
    authStore.isAuthenticated &&
    focusReviewStore.isFocusTopicReady
)

const focusTabBadgeGlowClass = computed(() => {
  if (!showFocusReviewBadge.value) return ''
  const phase =
    focusReviewStore.streamPhase !== 'idle'
      ? focusReviewStore.streamPhase
      : rootConceptReviewStore.streamPhase
  if (phase === 'streaming') return 'tab-rec-badge-wrap--streaming'
  if (phase === 'requesting') return 'tab-rec-badge-wrap--requesting'
  return 'tab-rec-badge-wrap--idle'
})

/** Show "Tab推荐" indicator when topic fixed—AI ready for inline recommendations (edit node, press Tab) */
const showInlineRecReady = computed(() => !isConceptMap.value && inlineRecStore.isReady)

/**
 * Tab rec badge ring matches inline SSE store (`streamPhase`):
 * requesting = blue traveling ring, streaming = green traveling ring,
 * idle = solid green ring (ready / stream finished / no request in flight).
 */
const tabRecBadgeGlowClass = computed(() => {
  if (!showInlineRecReady.value) return ''
  const phase = inlineRecStore.streamPhase
  if (phase === 'streaming') return 'tab-rec-badge-wrap--streaming'
  if (phase === 'requesting') return 'tab-rec-badge-wrap--requesting'
  return 'tab-rec-badge-wrap--idle'
})

// Model display names
const modelDisplayNames: Record<string, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

// Get model state
const getModelState = (modelKey: string) => {
  return llmResultsStore.modelStates[modelKey] || 'idle'
}

// Check if model is the currently selected one
const isSelectedModel = (modelKey: string) => {
  return llmResultsStore.selectedModel === modelKey
}

// Check if model has valid result (for clicking)
const _canSwitchTo = (modelKey: string) => {
  const state = getModelState(modelKey)
  return state === 'ready' && !isSelectedModel(modelKey)
}

// Handle model click
function handleModelClick(modelKey: string) {
  const state = getModelState(modelKey)

  if (state === 'ready') {
    switchToModel(modelKey)
    return
  }

  if (state === 'idle') {
    if (isSelectedModel(modelKey)) {
      llmResultsStore.setSelectedModel(null)
    } else {
      llmResultsStore.setSelectedModel(modelKey)
    }
  }
}

// Tooltip content based on state
function getTooltipContent(modelKey: string): string {
  const state = getModelState(modelKey)
  const displayName = modelDisplayNames[modelKey]

  const name = displayName ?? modelKey

  switch (state) {
    case 'loading':
      return String(t('aiModel.tooltip.generating', { name }))
    case 'ready':
      if (isSelectedModel(modelKey)) {
        return String(t('aiModel.tooltip.showingResult', { name }))
      }
      return String(t('aiModel.tooltip.clickSwitch', { name }))
    case 'error':
      return String(t('aiModel.tooltip.modelFailed', { name }))
    default:
      if (isSelectedModel(modelKey)) {
        return String(t('aiModel.tooltip.clickDeselect', { name }))
      }
      return String(t('aiModel.tooltip.clickSelect', { name }))
  }
}

// Model-specific colors (shared with NodePalettePanel)
const modelColors = LLM_MODEL_COLORS

// Button class based on state
function getButtonClass(modelKey: string): string {
  const state = getModelState(modelKey)
  const classes = ['model-btn', `model-btn-${modelKey}`]

  if (state === 'loading') {
    classes.push('loading')
  } else if (state === 'ready') {
    classes.push('ready')
    if (isSelectedModel(modelKey)) {
      classes.push('selected')
    }
  } else if (state === 'error') {
    classes.push('error')
  } else if (state === 'idle' && isSelectedModel(modelKey)) {
    classes.push('selected', 'blink-selected')
  }

  return classes.join(' ')
}

// Get button style based on model
function getButtonStyle(modelKey: string) {
  const colors = modelColors[modelKey]
  if (!colors) return {}

  const state = getModelState(modelKey)
  if (state === 'idle') {
    return {
      backgroundColor: colors.bg,
      borderColor: colors.border,
      color: colors.text,
    }
  }
  return {}
}
</script>

<template>
  <div class="ai-model-selector z-20 max-w-full min-w-0">
    <div class="glass-container px-3 py-1.5 flex items-center gap-3">
      <!-- Label with icon (hidden for concept map — single AI control only) -->
      <div
        v-if="!isConceptMap"
        class="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 shrink-0"
      >
        <Sparkles class="w-3.5 h-3.5 text-purple-500" />
        <span>{{ t('aiModel.label') }}</span>
      </div>

      <!-- Concept map: intrinsic width only (picker sits beside us in bottom bar; avoid flex-1 overlap) -->
      <div
        v-if="isConceptMap"
        class="flex gap-2 shrink-0 justify-center items-center"
      >
        <ElTooltip
          :content="
            llmResultsStore.selectedModel ? t('aiModel.conceptAiOn') : t('aiModel.conceptAiOff')
          "
          placement="top"
        >
          <button
            type="button"
            class="concept-ai-toggle-btn"
            :class="{ 'concept-ai-toggle-btn--on': llmResultsStore.selectedModel }"
            @click="toggleConceptMapAi"
          >
            <span class="font-semibold">{{ t('aiModel.enableAi') }}</span>
          </button>
        </ElTooltip>
        <ElTooltip
          v-if="showFocusReviewBadge"
          :content="t('aiModel.tabFocusTooltip')"
          placement="top"
        >
          <span
            class="tab-rec-badge-wrap inline-flex"
            :class="focusTabBadgeGlowClass"
          >
            <span class="tab-rec-badge-inner relationship-ready-badge">{{
              t('aiModel.tabFocusBadge')
            }}</span>
          </span>
        </ElTooltip>
      </div>
      <div
        v-else
        class="flex gap-1 flex-1 justify-center min-w-0"
      >
        <ElTooltip
          v-for="modelKey in llmResultsStore.models"
          :key="modelKey"
          :content="getTooltipContent(modelKey)"
          placement="top"
        >
          <button
            :class="getButtonClass(modelKey)"
            :style="getButtonStyle(modelKey)"
            :disabled="getModelState(modelKey) === 'loading'"
            @click="handleModelClick(modelKey)"
          >
            <span class="model-btn-content">
              <!-- Icon: errors only (loading uses border animation, no spinner) -->
              <span class="btn-icon">
                <X
                  v-if="getModelState(modelKey) === 'error'"
                  class="w-3.5 h-3.5"
                />
              </span>
              <span class="btn-label">{{ modelDisplayNames[modelKey] }}</span>
            </span>
          </button>
        </ElTooltip>
      </div>

      <!-- 关系 ready indicator (concept map: AI ready for link generation) - right of buttons -->
      <ElTooltip
        v-if="showRelationshipReady && !conceptMapTopToolbar"
        :content="t('aiModel.relationshipsTooltip')"
        placement="top"
      >
        <span class="relationship-ready-badge">{{ t('aiModel.relationshipsBadge') }}</span>
      </ElTooltip>

      <!-- Inline rec ready indicator (thinking maps: edit node, press Tab for AI recommendations) -->
      <ElTooltip
        v-if="showInlineRecReady"
        :content="t('aiModel.inlineRecTooltip')"
        placement="top"
      >
        <span
          class="tab-rec-badge-wrap inline-flex"
          :class="tabRecBadgeGlowClass"
        >
          <span class="tab-rec-badge-inner relationship-ready-badge">{{
            t('aiModel.tabRecBadge')
          }}</span>
        </span>
      </ElTooltip>

      <!-- Ready count indicator (hidden for concept map — no multi-model autocomplete) -->
      <div
        v-if="!isConceptMap && (llmResultsStore.isGenerating || llmResultsStore.hasAnyResults)"
        class="text-[10px] text-gray-500 dark:text-gray-400"
      >
        <span v-if="llmResultsStore.isGenerating">
          {{ llmResultsStore.successCount }}/{{
            llmResultsStore.totalModels ?? llmResultsStore.models.length
          }}
        </span>
        <span
          v-else-if="llmResultsStore.hasAnyResults"
          class="text-green-600 dark:text-green-400"
        >
          {{ t('aiModel.readyCount', { count: llmResultsStore.successCount }) }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
@property --model-ring-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

@property --tab-rec-border-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

/* Transparent container - no background */
.glass-container {
  background: transparent;
}

.tab-rec-badge-wrap {
  position: relative;
  border-radius: 6px;
  vertical-align: middle;
}

.tab-rec-badge-wrap--idle,
.tab-rec-badge-wrap--requesting,
.tab-rec-badge-wrap--streaming {
  padding: 2px;
}

.tab-rec-badge-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 2px;
  --tab-rec-border-angle: 0deg;
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: tab-rec-border-travel 2.5s linear infinite;
  transition: opacity 0.15s ease;
}

.tab-rec-badge-wrap--idle::before {
  opacity: 1;
  animation: none;
  background: #22c55e;
}

.tab-rec-badge-wrap--requesting::before {
  opacity: 1;
  background: conic-gradient(
    from var(--tab-rec-border-angle) at 50% 50%,
    rgba(16, 185, 129, 0.15) 0deg,
    rgba(16, 185, 129, 0.08) 50deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 230deg,
    rgba(16, 185, 129, 0.08) 310deg,
    rgba(16, 185, 129, 0.15) 360deg
  );
}

.tab-rec-badge-wrap--streaming::before {
  opacity: 1;
  background: conic-gradient(
    from var(--tab-rec-border-angle) at 50% 50%,
    rgba(16, 185, 129, 0.15) 0deg,
    rgba(16, 185, 129, 0.08) 50deg,
    #86efac 130deg,
    #22c55e 180deg,
    #4ade80 230deg,
    rgba(16, 185, 129, 0.08) 310deg,
    rgba(16, 185, 129, 0.15) 360deg
  );
}

:global(.dark) .tab-rec-badge-wrap--idle::before {
  background: #34d399;
}

:global(.dark) .tab-rec-badge-wrap--requesting::before {
  background: conic-gradient(
    from var(--tab-rec-border-angle) at 50% 50%,
    rgba(52, 211, 153, 0.12) 0deg,
    rgba(31, 41, 55, 0.9) 50deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 230deg,
    rgba(31, 41, 55, 0.9) 310deg,
    rgba(52, 211, 153, 0.12) 360deg
  );
}

:global(.dark) .tab-rec-badge-wrap--streaming::before {
  background: conic-gradient(
    from var(--tab-rec-border-angle) at 50% 50%,
    rgba(52, 211, 153, 0.12) 0deg,
    rgba(31, 41, 55, 0.9) 50deg,
    #4ade80 130deg,
    #16a34a 180deg,
    #86efac 230deg,
    rgba(31, 41, 55, 0.9) 310deg,
    rgba(52, 211, 153, 0.12) 360deg
  );
}

.tab-rec-badge-inner {
  position: relative;
  z-index: 1;
}

@keyframes tab-rec-border-travel {
  to {
    --tab-rec-border-angle: 360deg;
  }
}

.relationship-ready-badge {
  font-size: 10px;
  font-weight: 600;
  color: #10b981;
  background: rgba(16, 185, 129, 0.12);
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.dark .relationship-ready-badge {
  color: #34d399;
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.25);
}

.dark .glass-container {
  background: transparent;
}

.concept-ai-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(139, 92, 246, 0.35);
  background: rgba(139, 92, 246, 0.12);
  color: #7c3aed;
  cursor: pointer;
  transition:
    background 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.concept-ai-toggle-btn:hover {
  background: rgba(139, 92, 246, 0.2);
}

.concept-ai-toggle-btn--on {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.18);
  color: #047857;
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.35);
}

.dark .concept-ai-toggle-btn {
  border-color: rgba(167, 139, 250, 0.45);
  background: rgba(139, 92, 246, 0.2);
  color: #c4b5fd;
}

.dark .concept-ai-toggle-btn--on {
  border-color: #34d399;
  background: rgba(16, 185, 129, 0.22);
  color: #6ee7b7;
}

.model-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border: 1px solid rgba(229, 231, 235, 0.5);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 11px;
  font-weight: 500;
  color: #4b5563;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}

.model-btn-content {
  display: contents;
}

.model-btn .btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 12px;
  min-height: 12px;
}

.model-btn .btn-icon:empty {
  display: none;
}

.model-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Model-specific idle state colors */
.model-btn-qwen {
  border-color: rgba(99, 102, 241, 0.4) !important;
  background-color: rgba(99, 102, 241, 0.15) !important;
  color: #6366f1 !important;
}

.model-btn-deepseek {
  border-color: rgba(16, 185, 129, 0.4) !important;
  background-color: rgba(16, 185, 129, 0.15) !important;
  color: #10b981 !important;
}

.model-btn-doubao {
  border-color: rgba(249, 115, 22, 0.4) !important;
  background-color: rgba(249, 115, 22, 0.15) !important;
  color: #f97316 !important;
}

/* Loading: model-colored traveling border, solid inner (no spinner) */
.model-btn.loading {
  border-color: transparent !important;
  background-color: transparent !important;
  padding: 2px;
  cursor: wait;
  overflow: visible;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.model-btn.loading::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 7px;
  padding: 2px;
  --model-ring-angle: 0deg;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: model-ring-spin 2.5s linear infinite;
}

.model-btn.loading .model-btn-content {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px;
  border-radius: 5px;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.model-btn.loading.model-btn-qwen::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(99, 102, 241, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #a5b4fc 130deg,
    #6366f1 180deg,
    #818cf8 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(99, 102, 241, 0.2) 360deg
  );
}

.model-btn.loading.model-btn-qwen .model-btn-content {
  background-color: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.28);
  color: #6366f1;
}

.model-btn.loading.model-btn-deepseek::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #6ee7b7 130deg,
    #10b981 180deg,
    #34d399 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(16, 185, 129, 0.2) 360deg
  );
}

.model-btn.loading.model-btn-deepseek .model-btn-content {
  background-color: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: #10b981;
}

.model-btn.loading.model-btn-doubao::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(249, 115, 22, 0.2) 0deg,
    rgba(226, 232, 240, 0.85) 55deg,
    #fdba74 130deg,
    #f97316 180deg,
    #fb923c 230deg,
    rgba(226, 232, 240, 0.85) 305deg,
    rgba(249, 115, 22, 0.2) 360deg
  );
}

.model-btn.loading.model-btn-doubao .model-btn-content {
  background-color: rgba(249, 115, 22, 0.12);
  border: 1px solid rgba(249, 115, 22, 0.28);
  color: #f97316;
}

@keyframes model-ring-spin {
  to {
    --model-ring-angle: 360deg;
  }
}

/* Ready state (has result, can click) */
.model-btn.ready {
  border-color: #10b981;
  background-color: rgba(209, 250, 229, 0.8);
  backdrop-filter: blur(8px);
  color: #065f46;
  cursor: pointer;
  animation: glow 2s ease-in-out 1;
}

/* Selected state (currently displayed result) */
.model-btn.selected {
  border-color: #3b82f6;
  background-color: rgba(219, 234, 254, 0.9);
  backdrop-filter: blur(8px);
  color: #1d4ed8;
  animation: none;
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.3),
    0 4px 12px rgba(59, 130, 246, 0.2);
}

/* Blinking effect when selected for concept map relationship generation */
.model-btn.blink-selected {
  animation: blink-selected 1.5s ease-in-out infinite;
}

@keyframes blink-selected {
  0%,
  100% {
    box-shadow:
      0 0 0 2px rgba(59, 130, 246, 0.3),
      0 4px 12px rgba(59, 130, 246, 0.2);
    opacity: 1;
  }
  50% {
    box-shadow:
      0 0 0 4px rgba(59, 130, 246, 0.5),
      0 0 20px rgba(59, 130, 246, 0.4);
    opacity: 0.95;
  }
}

/* Error state */
.model-btn.error {
  border-color: #ef4444;
  background-color: rgba(254, 226, 226, 0.8);
  backdrop-filter: blur(8px);
  color: #991b1b;
  cursor: not-allowed;
  opacity: 0.7;
}

/* Glow animation for newly ready results */
@keyframes glow {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
  50% {
    box-shadow: 0 0 12px 4px rgba(16, 185, 129, 0.4);
  }
}

/* Dark mode */
.dark .model-btn {
  background: rgba(55, 65, 81, 0.6);
  backdrop-filter: blur(8px);
  border-color: rgba(75, 85, 99, 0.5);
  color: #d1d5db;
}

.dark .model-btn-qwen {
  border-color: rgba(99, 102, 241, 0.5) !important;
  background-color: rgba(99, 102, 241, 0.2) !important;
  color: #818cf8 !important;
}

.dark .model-btn-deepseek {
  border-color: rgba(16, 185, 129, 0.5) !important;
  background-color: rgba(16, 185, 129, 0.2) !important;
  color: #34d399 !important;
}

.dark .model-btn-doubao {
  border-color: rgba(249, 115, 22, 0.5) !important;
  background-color: rgba(249, 115, 22, 0.2) !important;
  color: #fb923c !important;
}

.dark .model-btn:hover:not(:disabled) {
  border-color: #60a5fa;
  background-color: #1e3a5f;
  color: #93c5fd;
}

.dark .model-btn.loading.model-btn-qwen::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(99, 102, 241, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #818cf8 130deg,
    #6366f1 180deg,
    #a78bfa 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(99, 102, 241, 0.25) 360deg
  );
}

.dark .model-btn.loading.model-btn-qwen .model-btn-content {
  background-color: rgba(99, 102, 241, 0.18);
  border-color: rgba(129, 140, 248, 0.35);
  color: #a5b4fc;
}

.dark .model-btn.loading.model-btn-deepseek::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(16, 185, 129, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #34d399 130deg,
    #10b981 180deg,
    #6ee7b7 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(16, 185, 129, 0.25) 360deg
  );
}

.dark .model-btn.loading.model-btn-deepseek .model-btn-content {
  background-color: rgba(16, 185, 129, 0.18);
  border-color: rgba(52, 211, 153, 0.35);
  color: #34d399;
}

.dark .model-btn.loading.model-btn-doubao::before {
  background: conic-gradient(
    from var(--model-ring-angle) at 50% 50%,
    rgba(249, 115, 22, 0.25) 0deg,
    rgba(31, 41, 55, 0.95) 55deg,
    #fb923c 130deg,
    #f97316 180deg,
    #fdba74 230deg,
    rgba(31, 41, 55, 0.95) 305deg,
    rgba(249, 115, 22, 0.25) 360deg
  );
}

.dark .model-btn.loading.model-btn-doubao .model-btn-content {
  background-color: rgba(249, 115, 22, 0.18);
  border-color: rgba(251, 146, 60, 0.35);
  color: #fb923c;
}

.dark .model-btn.ready {
  border-color: #10b981;
  background-color: #064e3b;
  color: #6ee7b7;
}

.dark .model-btn.selected {
  border-color: #60a5fa;
  background-color: #1e3a5f;
  color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.3);
}

.dark .model-btn.blink-selected {
  animation: blink-selected-dark 1.5s ease-in-out infinite;
}

@keyframes blink-selected-dark {
  0%,
  100% {
    box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.3);
    opacity: 1;
  }
  50% {
    box-shadow:
      0 0 0 4px rgba(96, 165, 250, 0.5),
      0 0 20px rgba(96, 165, 250, 0.35);
    opacity: 0.95;
  }
}

.dark .model-btn.error {
  border-color: #ef4444;
  background-color: #450a0a;
  color: #fca5a5;
}

@keyframes glow-dark {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(110, 231, 183, 0);
  }
  50% {
    box-shadow: 0 0 12px 4px rgba(110, 231, 183, 0.4);
  }
}

.dark .model-btn.ready {
  animation-name: glow-dark;
}
</style>
