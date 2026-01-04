<script setup lang="ts">
/**
 * ChatInput - Chat input with upload buttons and character counter
 */
import { computed } from 'vue'

import { ArrowRight, FileText, Image as ImageIcon } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
  maxLength?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'uploadImage'): void
  (e: 'uploadDocument'): void
}>()

const maxLen = computed(() => props.maxLength ?? 200)

const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
})

const canSend = computed(() => inputValue.value.trim() && !props.disabled)

function handleKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canSend.value) {
      emit('send')
    }
  }
}

function handleSend() {
  if (canSend.value) {
    emit('send')
  }
}
</script>

<template>
  <div class="chat-input rounded-xl border border-gray-200 p-4 bg-white shadow-sm">
    <textarea
      v-model="inputValue"
      placeholder="请输入内容..."
      class="w-full border-none outline-none resize-none min-h-[80px] text-gray-800"
      :maxlength="maxLen"
      :disabled="disabled"
      @keypress="handleKeyPress"
    />

    <div class="flex justify-between items-center mt-2">
      <!-- Upload buttons -->
      <div class="flex space-x-4">
        <button
          class="flex items-center text-blue-600 hover:text-blue-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="disabled"
          @click="emit('uploadImage')"
        >
          <ImageIcon class="w-3.5 h-3.5 mr-1" />
          上传图片
        </button>
        <button
          class="flex items-center text-blue-600 hover:text-blue-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="disabled"
          @click="emit('uploadDocument')"
        >
          <FileText class="w-3.5 h-3.5 mr-1" />
          上传文档
        </button>
      </div>

      <!-- Send area -->
      <div class="flex items-center space-x-3">
        <span class="text-xs text-gray-500">{{ inputValue.length }}/{{ maxLen }}</span>
        <button
          class="w-9 h-9 rounded-full flex items-center justify-center text-white transition-colors"
          :class="canSend ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-300 cursor-not-allowed'"
          :disabled="!canSend"
          @click="handleSend"
        >
          <ArrowRight class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
