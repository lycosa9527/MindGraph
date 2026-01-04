<script setup lang="ts">
/**
 * MindMate Panel - AI assistant chat interface
 * Uses useMindMate composable for SSE streaming
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { useLanguage, useMindMate, useNotifications } from '@/composables'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t, isZh } = useLanguage()
const notify = useNotifications()

// Use MindMate composable for SSE streaming
const mindMate = useMindMate({
  language: isZh.value ? 'zh' : 'en',
  onError: (error) => {
    notify.error(error)
  },
})

// Local state
const inputText = ref('')
const messagesContainer = ref<HTMLDivElement | null>(null)

// Computed for loading state
const isLoading = computed(() => mindMate.isLoading.value || mindMate.isStreaming.value)

// Send welcome message on mount
onMounted(() => {
  if (!mindMate.hasMessages.value) {
    mindMate.sendGreeting()
  }
})

// Watch for new messages to scroll
watch(
  () => mindMate.messages.value.length,
  async () => {
    await scrollToBottom()
  }
)

// Also scroll when streaming updates content
watch(
  () => mindMate.lastMessage.value?.content,
  async () => {
    if (mindMate.isStreaming.value) {
      await scrollToBottom()
    }
  }
)

// Send message using composable
async function sendMessage() {
  if (!inputText.value.trim() || isLoading.value) return

  const message = inputText.value.trim()
  inputText.value = ''

  await mindMate.sendMessage(message)
}

// Handle keyboard
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

// Scroll to bottom of messages
async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Clear chat
function clearChat() {
  mindMate.clearMessages()
  mindMate.sendGreeting()
}

// Format timestamp
function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div
    class="mindmate-panel bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-lg flex flex-col"
  >
    <!-- Header -->
    <div
      class="panel-header h-12 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700"
    >
      <div class="flex items-center gap-2">
        <div
          class="w-8 h-8 bg-gradient-to-br from-primary-400 to-purple-500 rounded-lg flex items-center justify-center"
        >
          <el-icon class="text-white"><ChatDotRound /></el-icon>
        </div>
        <h3 class="font-medium text-gray-800 dark:text-white">
          {{ t('panel.mindmate') }}
        </h3>
      </div>
      <div class="flex items-center gap-1">
        <el-tooltip :content="isZh ? '清空聊天' : 'Clear chat'">
          <el-button
            text
            circle
            @click="clearChat"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </el-tooltip>
        <el-button
          text
          circle
          @click="emit('close')"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Messages -->
    <div
      ref="messagesContainer"
      class="messages-container flex-1 overflow-y-auto p-4 space-y-4"
    >
      <div
        v-for="message in mindMate.messages.value"
        :key="message.id"
        class="message flex gap-3"
        :class="message.role === 'user' ? 'flex-row-reverse' : ''"
      >
        <!-- Avatar -->
        <div
          class="avatar w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center"
          :class="
            message.role === 'user'
              ? 'bg-primary-500'
              : 'bg-gradient-to-br from-primary-400 to-purple-500'
          "
        >
          <el-icon class="text-white">
            <User v-if="message.role === 'user'" />
            <ChatDotRound v-else />
          </el-icon>
        </div>

        <!-- Content -->
        <div
          class="message-content max-w-[80%] rounded-lg p-3"
          :class="[
            message.role === 'user'
              ? 'bg-primary-500 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-white',
            message.isStreaming ? 'streaming' : ''
          ]"
        >
          <p class="whitespace-pre-wrap text-sm">{{ message.content }}</p>
          <!-- Streaming cursor -->
          <span
            v-if="message.isStreaming"
            class="inline-block w-2 h-4 bg-current animate-pulse ml-0.5"
          />
          <p
            class="text-xs mt-1 opacity-60"
            :class="message.role === 'user' ? 'text-right' : ''"
          >
            {{ formatTime(message.timestamp) }}
          </p>
        </div>
      </div>

      <!-- Loading indicator (before first response) -->
      <div
        v-if="mindMate.isLoading.value && !mindMate.isStreaming.value"
        class="message flex gap-3"
      >
        <div
          class="avatar w-8 h-8 rounded-lg bg-gradient-to-br from-primary-400 to-purple-500 flex items-center justify-center"
        >
          <el-icon class="text-white"><ChatDotRound /></el-icon>
        </div>
        <div class="message-content bg-gray-100 dark:bg-gray-700 rounded-lg p-3">
          <div class="flex gap-1">
            <span
              class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style="animation-delay: 0ms"
            />
            <span
              class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style="animation-delay: 150ms"
            />
            <span
              class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style="animation-delay: 300ms"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="input-area p-4 border-t border-gray-200 dark:border-gray-700">
      <div class="flex gap-2">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :placeholder="isZh ? '输入消息...' : 'Type a message...'"
          :disabled="isLoading"
          @keydown="handleKeydown"
        />
        <el-button
          type="primary"
          :disabled="!inputText.trim() || isLoading"
          @click="sendMessage"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mindmate-panel {
  height: 100%;
}

.messages-container {
  scroll-behavior: smooth;
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}
</style>
