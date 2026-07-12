<script setup lang="ts">
/**
 * Compact Qwen / DeepSeek / Doubao row for Mobile Kitty — mirrors desktop AIModelSelector.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { LLM_MODEL_COLORS } from '@/config/llmModelColors'
import { useLLMResultsStore, type LLMModel } from '@/stores/llmResults'

const props = defineProps<{
  onModelChange?: () => void
}>()

const { t } = useLanguage()
const llmResultsStore = useLLMResultsStore()

const MODEL_LABELS: Record<LLMModel, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

const models = computed(() => llmResultsStore.models as readonly LLMModel[])

function isSelected(model: LLMModel): boolean {
  return llmResultsStore.selectedModel === model
}

function modelState(model: LLMModel): string {
  return llmResultsStore.modelStates[model] ?? 'idle'
}

/** Always brand-colored like desktop idle pills (not gray when unselected). */
function buttonStyle(model: LLMModel): Record<string, string> {
  const colors = LLM_MODEL_COLORS[model]
  if (!colors) {
    return {}
  }
  const state = modelState(model)
  if (state === 'ready' && isSelected(model)) {
    return {
      backgroundColor: 'rgba(219, 234, 254, 0.9)',
      borderColor: '#3b82f6',
      color: '#1d4ed8',
    }
  }
  if (state === 'ready') {
    return {
      backgroundColor: 'rgba(209, 250, 229, 0.8)',
      borderColor: '#10b981',
      color: '#065f46',
    }
  }
  return {
    backgroundColor: colors.bg,
    borderColor: colors.border,
    color: colors.text,
  }
}

async function onModelClick(model: LLMModel): Promise<void> {
  const state = modelState(model)
  if (state === 'ready') {
    await llmResultsStore.switchToModel(model)
    props.onModelChange?.()
    return
  }
  if (state === 'loading') {
    return
  }
  if (isSelected(model)) {
    llmResultsStore.setSelectedModel(null)
  } else {
    llmResultsStore.setSelectedModel(model)
  }
  props.onModelChange?.()
}
</script>

<template>
  <div
    class="kitty-llm-row"
    role="group"
    :aria-label="t('mobile.kittyLlmRowAria', '选择 AI 模型')"
  >
    <button
      v-for="model in models"
      :key="model"
      type="button"
      class="kitty-llm-btn"
      :class="{
        'kitty-llm-btn--selected': isSelected(model),
        'kitty-llm-btn--ready': modelState(model) === 'ready',
        'kitty-llm-btn--loading': modelState(model) === 'loading',
      }"
      :style="buttonStyle(model)"
      :aria-pressed="isSelected(model)"
      :disabled="modelState(model) === 'loading'"
      @click="onModelClick(model)"
    >
      {{ MODEL_LABELS[model] }}
    </button>
  </div>
</template>

<style scoped>
.kitty-llm-row {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.375rem;
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
  padding: 0.15rem 0;
}

.kitty-llm-btn {
  flex: 0 0 auto;
  box-sizing: border-box;
  width: auto;
  min-width: 0;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  border: 1px solid;
  font-size: 0.6875rem;
  font-weight: 500;
  line-height: 1.25;
  white-space: nowrap;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.kitty-llm-btn--selected:not(.kitty-llm-btn--ready) {
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.3),
    0 2px 8px rgba(59, 130, 246, 0.18);
}

.kitty-llm-btn--selected.kitty-llm-btn--ready {
  box-shadow:
    0 0 0 2px rgba(59, 130, 246, 0.3),
    0 4px 12px rgba(59, 130, 246, 0.2);
}

.kitty-llm-btn:disabled {
  opacity: 0.55;
  cursor: default;
}

.kitty-llm-btn--loading {
  animation: kitty-llm-pulse 1.1s ease-in-out infinite;
}

@keyframes kitty-llm-pulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}
</style>
