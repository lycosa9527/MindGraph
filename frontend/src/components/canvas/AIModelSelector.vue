<script setup lang="ts">
/**
 * AIModelSelector - Bottom center AI model selection
 * Shows available AI models: Qwen, DeepSeek, Doubao
 */
import { ref } from 'vue'

import { ElTooltip } from 'element-plus'
import { Sparkles } from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const { isZh } = useLanguage()

const models = ['Qwen', 'DeepSeek', 'Doubao']

const selectedModel = ref<string>('Qwen')

function selectModel(modelName: string) {
  selectedModel.value = modelName
  emit('model-change', modelName)
}

const emit = defineEmits<{
  (e: 'model-change', model: string): void
}>()
</script>

<template>
  <div class="ai-model-selector absolute left-1/2 bottom-4 transform -translate-x-1/2 z-20">
    <div
      class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg px-3 py-2 flex items-center gap-3"
    >
      <!-- Label with icon -->
      <div class="flex items-center gap-1.5 text-sm font-medium text-gray-600 dark:text-gray-300">
        <Sparkles class="w-4 h-4 text-purple-500" />
        <span>{{ isZh ? 'AI模型' : 'AI Model' }}</span>
      </div>

      <!-- Model buttons -->
      <div class="flex gap-1.5">
        <ElTooltip
          v-for="model in models"
          :key="model"
          :content="isZh ? `使用 ${model} 模型` : `Use ${model} model`"
          placement="top"
        >
          <button
            class="model-btn"
            :class="{ active: selectedModel === model }"
            @click="selectModel(model)"
          >
            {{ model }}
          </button>
        </ElTooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-btn {
  padding: 6px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 12px;
  font-weight: 500;
  color: #4b5563;
  white-space: nowrap;
}

.model-btn:hover {
  border-color: #3b82f6;
  background-color: #eff6ff;
  color: #1d4ed8;
}

.model-btn.active {
  border-color: #3b82f6;
  background-color: #dbeafe;
  color: #1d4ed8;
}

/* Dark mode */
.dark .model-btn {
  background: #374151;
  border-color: #4b5563;
  color: #d1d5db;
}

.dark .model-btn:hover {
  border-color: #60a5fa;
  background-color: #1e3a5f;
  color: #93c5fd;
}

.dark .model-btn.active {
  border-color: #60a5fa;
  background-color: #1e3a5f;
  color: #93c5fd;
}
</style>
