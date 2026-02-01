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
import { computed, watch } from 'vue'

import { ElTooltip } from 'element-plus'

import { Loader2, Sparkles, X } from 'lucide-vue-next'

import { useAutoComplete, useLanguage } from '@/composables'
import { useLLMResultsStore } from '@/stores'

const { isZh } = useLanguage()
const { switchToModel } = useAutoComplete()
const llmResultsStore = useLLMResultsStore()

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
    // Switch to this model's result
    switchToModel(modelKey)
  }
}

// Tooltip content based on state
function getTooltipContent(modelKey: string): string {
  const state = getModelState(modelKey)
  const displayName = modelDisplayNames[modelKey]

  switch (state) {
    case 'loading':
      return isZh.value ? `${displayName} 生成中...` : `${displayName} generating...`
    case 'ready':
      if (isSelectedModel(modelKey)) {
        return isZh.value
          ? `当前显示 ${displayName} 结果`
          : `Currently showing ${displayName} result`
      }
      return isZh.value
        ? `点击切换到 ${displayName} 结果`
        : `Click to switch to ${displayName} result`
    case 'error':
      return isZh.value ? `${displayName} 生成失败` : `${displayName} generation failed`
    default:
      return isZh.value ? `${displayName} 模型` : `${displayName} model`
  }
}

// Model-specific colors
const modelColors: Record<string, { bg: string; border: string; text: string }> = {
  qwen: {
    bg: 'rgba(99, 102, 241, 0.15)', // Indigo
    border: 'rgba(99, 102, 241, 0.4)',
    text: '#6366f1',
  },
  deepseek: {
    bg: 'rgba(16, 185, 129, 0.15)', // Green
    border: 'rgba(16, 185, 129, 0.4)',
    text: '#10b981',
  },
  doubao: {
    bg: 'rgba(249, 115, 22, 0.15)', // Orange
    border: 'rgba(249, 115, 22, 0.4)',
    text: '#f97316',
  },
}

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

// Should show glow animation
const _glowingModels = computed(() => {
  return Object.entries(llmResultsStore.modelStates)
    .filter(([_, state]) => state === 'ready')
    .map(([model]) => model)
})

// Watch for new ready models to trigger glow animation
const _recentlyReady = computed(() => new Set<string>())
watch(
  () => llmResultsStore.modelStates,
  (newStates, oldStates) => {
    for (const [model, state] of Object.entries(newStates)) {
      if (state === 'ready' && oldStates?.[model] === 'loading') {
        // Just became ready - could trigger animation here
        console.log(`[AIModelSelector] ${model} just became ready`)
      }
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="ai-model-selector absolute left-1/2 bottom-4 transform -translate-x-1/2 z-20">
    <div
      class="glass-container rounded-xl shadow-lg px-3 py-2 flex items-center gap-3"
    >
      <!-- Label with icon -->
      <div class="flex items-center gap-1.5 text-sm font-medium text-gray-600 dark:text-gray-300">
        <Sparkles class="w-4 h-4 text-purple-500" />
        <span>{{ isZh ? 'AI模型' : 'AI Model' }}</span>
      </div>

      <!-- Model buttons -->
      <div class="flex gap-1.5">
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
            <!-- Icon based on state -->
            <span class="btn-icon">
              <Loader2
                v-if="getModelState(modelKey) === 'loading'"
                class="w-3.5 h-3.5 animate-spin"
              />
              <X
                v-else-if="getModelState(modelKey) === 'error'"
                class="w-3.5 h-3.5"
              />
            </span>

            <!-- Model name -->
            <span class="btn-label">{{ modelDisplayNames[modelKey] }}</span>
          </button>
        </ElTooltip>
      </div>

      <!-- Ready count indicator -->
      <div
        v-if="llmResultsStore.isGenerating || llmResultsStore.hasAnyResults"
        class="text-xs text-gray-500 dark:text-gray-400 ml-1"
      >
        <span v-if="llmResultsStore.isGenerating"> {{ llmResultsStore.successCount }}/3 </span>
        <span
          v-else-if="llmResultsStore.hasAnyResults"
          class="text-green-600 dark:text-green-400"
        >
          {{
            isZh ? `${llmResultsStore.successCount}个就绪` : `${llmResultsStore.successCount} ready`
          }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Glassmorphism container */
.glass-container {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.dark .glass-container {
  background: rgba(31, 41, 55, 0.7);
  border-color: rgba(255, 255, 255, 0.1);
}

.model-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid rgba(229, 231, 235, 0.5);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 12px;
  font-weight: 500;
  color: #4b5563;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}

.model-btn .btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 14px;
  min-height: 14px;
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

/* Loading state */
.model-btn.loading {
  border-color: #fbbf24;
  background-color: rgba(254, 243, 199, 0.8);
  backdrop-filter: blur(8px);
  color: #92400e;
  cursor: wait;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
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
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3), 0 4px 12px rgba(59, 130, 246, 0.2);
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

.dark .model-btn.loading {
  border-color: #fbbf24;
  background-color: #451a03;
  color: #fcd34d;
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
