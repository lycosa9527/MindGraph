<script setup lang="ts">
/**
 * DebateInput - Input for user debater messages
 */
import { ref, computed } from 'vue'

import { ElButton, ElInput } from 'element-plus'

import { ElIcon } from 'element-plus'
import { Right } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'

const { isZh } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// State
// ============================================================================

const inputText = ref('')
const isSending = ref(false)

// ============================================================================
// Computed
// ============================================================================

const canSend = computed(() => inputText.value.trim().length > 0 && !isSending.value)

// ============================================================================
// Actions
// ============================================================================

async function sendMessage() {
  if (!canSend.value) return

  isSending.value = true
  try {
    await store.sendMessage(inputText.value.trim())
    inputText.value = ''
  } catch (error) {
    console.error('Error sending message:', error)
  } finally {
    isSending.value = false
  }
}

function handleKeydown(e: Event | KeyboardEvent) {
  if (!(e instanceof KeyboardEvent)) return
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    if (canSend.value) {
      sendMessage()
    }
  }
}
</script>

<template>
  <div class="debate-input px-6 py-4 bg-white border-t border-gray-200">
    <div class="max-w-4xl mx-auto flex items-end gap-3">
      <ElInput
        v-model="inputText"
        type="textarea"
        :rows="2"
        :placeholder="isZh ? '输入你的发言... (Ctrl+Enter 发送)' : 'Enter your speech... (Ctrl+Enter to send)'"
        resize="vertical"
        @keydown="handleKeydown"
      />
      <ElButton
        type="primary"
        :disabled="!canSend"
        :loading="isSending"
        @click="sendMessage"
      >
        <ElIcon class="mr-1"><Right /></ElIcon>
        {{ isZh ? '发送' : 'Send' }}
      </ElButton>
    </div>
  </div>
</template>
