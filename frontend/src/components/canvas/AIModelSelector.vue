<script setup lang="ts">
/**
 * AIModelSelector - Bottom center AI model selection
 * Migrated from prototype MindGraphCanvasPage model selector
 */
import { ref } from 'vue'

interface AIModel {
  name: string
  icon: string
}

const models: AIModel[] = [
  { name: 'Qwen', icon: 'Q' },
  { name: 'DeepSeek', icon: 'D' },
  { name: 'Hunyuan', icon: 'H' },
  { name: 'Kimi', icon: 'K' },
  { name: 'Doubao', icon: '豆' },
]

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
  <div
    class="ai-model-selector absolute left-1/2 bottom-4 transform -translate-x-1/2 bg-white border border-gray-200 rounded-lg shadow-md p-2 flex items-center"
  >
    <div class="text-sm font-medium text-gray-700">选择AI模型：</div>
    <div class="flex gap-2 ml-3 overflow-x-auto hide-scrollbar">
      <button
        v-for="model in models"
        :key="model.name"
        class="px-3 py-1 border rounded-md hover:border-blue-400 hover:bg-blue-50 transition-colors text-xs font-medium text-gray-800 flex items-center gap-1 whitespace-nowrap"
        :class="selectedModel === model.name ? 'border-blue-400 bg-blue-50' : 'border-gray-200'"
        :title="`使用${model.name}模型`"
        @click="selectModel(model.name)"
      >
        <div
          class="w-5 h-5 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-[10px]"
        >
          {{ model.icon }}
        </div>
        <span>{{ model.name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}

.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
