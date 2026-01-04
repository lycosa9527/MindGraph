<script setup lang="ts">
/**
 * Prompt Input - AI prompt input field with autocomplete
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables'

const props = defineProps<{
  isLoading?: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', prompt: string): void
}>()

const { isZh } = useLanguage()

const promptText = ref('')
const isFocused = ref(false)

const placeholder = computed(() =>
  isZh.value
    ? '描述你想创建的图表，例如："请帮我画一张关于光合作用的思维导图"'
    : 'Describe the diagram you want to create, e.g., "Create a mind map about photosynthesis"'
)

function handleSubmit() {
  if (!promptText.value.trim() || props.isLoading) return
  emit('submit', promptText.value.trim())
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <div class="prompt-input-container">
    <div
      class="prompt-wrapper rounded-2xl p-1 transition-all duration-300"
      :class="
        isFocused
          ? 'bg-gradient-to-r from-primary-400 via-purple-500 to-pink-500 shadow-lg shadow-primary-500/20'
          : 'bg-gray-200 dark:bg-gray-700'
      "
    >
      <div class="bg-white dark:bg-gray-800 rounded-xl p-4 flex gap-3">
        <!-- Icon -->
        <div
          class="flex-shrink-0 w-10 h-10 bg-primary-100 dark:bg-primary-900 rounded-lg flex items-center justify-center"
        >
          <el-icon
            :size="20"
            class="text-primary-500"
          >
            <MagicStick />
          </el-icon>
        </div>

        <!-- Input -->
        <div class="flex-1">
          <textarea
            v-model="promptText"
            :placeholder="placeholder"
            class="w-full bg-transparent border-none outline-none resize-none text-gray-800 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 text-base"
            rows="2"
            :disabled="isLoading"
            @focus="isFocused = true"
            @blur="isFocused = false"
            @keydown="handleKeydown"
          />
        </div>

        <!-- Submit Button -->
        <div class="flex-shrink-0 flex items-end">
          <el-button
            type="primary"
            :loading="isLoading"
            :disabled="!promptText.trim()"
            circle
            @click="handleSubmit"
          >
            <el-icon v-if="!isLoading"><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- Helper Text -->
    <p class="text-center text-xs text-gray-400 dark:text-gray-500 mt-3">
      {{
        isZh
          ? '按 Enter 发送，Shift + Enter 换行'
          : 'Press Enter to send, Shift + Enter for new line'
      }}
    </p>
  </div>
</template>

<style scoped>
.prompt-input-container {
  max-width: 800px;
  margin: 0 auto;
}

textarea {
  font-family: inherit;
  line-height: 1.5;
}

textarea::-webkit-scrollbar {
  width: 4px;
}

textarea::-webkit-scrollbar-thumb {
  background: var(--mg-border-color);
  border-radius: 2px;
}
</style>
