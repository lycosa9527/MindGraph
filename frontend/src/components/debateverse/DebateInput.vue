<script setup lang="ts">
/**
 * DebateInput - Input section with message input and Next button
 */
import { computed, ref } from 'vue'

import { ElButton, ElInput } from 'element-plus'

import { ArrowRight } from '@element-plus/icons-vue'

import { Send } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'

const { t } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// Props
// ============================================================================

interface Props {
  isTriggeringNext?: boolean
  canTriggerNext?: boolean
  nextButtonText?: string
}

withDefaults(defineProps<Props>(), {
  isTriggeringNext: false,
  canTriggerNext: false,
  nextButtonText: '',
})

// ============================================================================
// Emits
// ============================================================================

const emit = defineEmits<{
  next: []
}>()

// ============================================================================
// State
// ============================================================================

const inputText = ref('')
const isSending = ref(false)

// ============================================================================
// Computed
// ============================================================================

const isViewer = computed(() => store.userRole === 'viewer')
const canSend = computed(() => {
  if (isViewer.value) return false
  return inputText.value.trim().length > 0 && !isSending.value && store.canUserSpeak
})

const inputPlaceholder = computed(() => {
  if (isViewer.value) {
    return t('debateverse.input.spectator')
  }
  if (!store.canUserSpeak) {
    return t('debateverse.input.waitTurn')
  }
  return t('debateverse.input.speechPlaceholder')
})

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

function handleNext() {
  emit('next')
}
</script>

<template>
  <!-- Message Input Section (Below debate section, includes input and Next button) -->
  <div class="debate-input px-6 pt-4 pb-10 bg-white border-t border-gray-200 flex-shrink-0">
    <div class="max-w-4xl mx-auto">
      <!-- Input Container (MindGraph fullpage style) -->
      <div class="input-container-fullpage">
        <!-- Text Input -->
        <div class="input-field-fullpage">
          <ElInput
            v-model="inputText"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="inputPlaceholder"
            :disabled="isViewer || !store.canUserSpeak"
            class="fullpage-textarea"
            @keydown="handleKeydown"
          />
        </div>

        <!-- Action buttons (right side) -->
        <div class="input-actions-fullpage">
          <!-- Send Button -->
          <ElButton
            type="primary"
            class="send-btn-fullpage"
            :disabled="!canSend"
            :loading="isSending"
            @click="sendMessage"
          >
            <Send :size="18" />
          </ElButton>

          <!-- Next Button -->
          <ElButton
            type="primary"
            class="next-btn-fullpage"
            :disabled="!canTriggerNext"
            :loading="isTriggeringNext || store.isStreaming"
            @click="handleNext"
          >
            <ArrowRight :size="18" />
            <span class="ml-1">{{ nextButtonText || t('debateverse.next.label') }}</span>
          </ElButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Import MindGraph input styles */
@import '@/components/panels/mindmate/mindmate.css';

/* Send Button - Remove any custom overrides, use MindGraph's styles from CSS import */

/* Next Button Styling (matches send button style) */
.next-btn-fullpage {
  flex-shrink: 0;
  width: auto;
  height: 40px;
  padding: 0 16px;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
}

.next-btn-fullpage:not(:disabled) {
  background: #3b82f6;
  color: #fff;
}

.next-btn-fullpage:not(:disabled):hover {
  background: #2563eb;
}

.next-btn-fullpage:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}
</style>
