<script setup lang="ts">
/**
 * ChatContainer - Main chat area with messages and typing indicator
 */
import { nextTick, ref, watch } from 'vue'

import { SuggestionBubbles } from '@/components/common'
import { SUGGESTION_PROMPTS, useChatStore } from '@/stores'

import ChatInput from './ChatInput.vue'
import ChatMessage from './ChatMessage.vue'

const chatStore = useChatStore()

const messagesContainerRef = ref<HTMLDivElement | null>(null)

// Scroll to bottom when messages change
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

watch(
  () => chatStore.isAiTyping,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

function scrollToBottom() {
  if (messagesContainerRef.value) {
    messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight
  }
}

function handleSuggestionClick(suggestion: string) {
  chatStore.setInputValue(suggestion)
}

function handleSend() {
  chatStore.sendMessage(chatStore.inputValue)
}

function handleCopy(messageId: string) {
  chatStore.copyMessage(messageId)
}

// AI robot image URL
const robotImageUrl =
  'https://space-static.coze.site/coze_space/7586606221064585514/upload/%E6%96%B0%E5%AF%B9%E8%AF%9D%281%29%281%29%281%29_536x662.png?sign=1768989628-231ab7c8de-0-26441aa331e9c26987be17f74685c0f95079054464622780e9f012aa077f9606'
const aiAvatarUrl = robotImageUrl
</script>

<template>
  <div class="chat-container flex flex-col h-full">
    <!-- Messages Area -->
    <div
      ref="messagesContainerRef"
      class="flex-1 overflow-y-auto p-8 bg-white"
    >
      <!-- Empty state with welcome -->
      <template v-if="!chatStore.hasMessages">
        <div class="flex flex-col items-center justify-center h-full">
          <img
            :src="robotImageUrl"
            alt="MindMate机器人"
            class="w-36 h-28 object-contain"
          />
          <div class="text-center mt-6">
            <div class="text-2xl font-medium text-gray-800 mb-2">你好</div>
            <div class="text-lg text-gray-600">我是你的虚拟教研伙伴MindMate</div>
          </div>
        </div>
      </template>

      <!-- Messages list -->
      <template v-else>
        <div class="space-y-6 max-w-3xl mx-auto">
          <ChatMessage
            v-for="message in chatStore.messages"
            :key="message.id"
            :message="message"
            :is-copied="chatStore.copiedMessageId === message.id"
            @copy="handleCopy"
          />

          <!-- Typing indicator -->
          <div
            v-if="chatStore.isAiTyping"
            class="flex justify-start"
          >
            <div class="flex items-start space-x-3 max-w-[80%]">
              <img
                :src="aiAvatarUrl"
                alt="AI头像"
                class="w-8 h-8 rounded-full object-cover mt-1"
              />
              <div
                class="bg-white text-gray-800 border border-gray-200 px-4 py-3 rounded-lg shadow-sm rounded-bl-none"
              >
                <div class="flex space-x-1">
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
        </div>
      </template>
    </div>

    <!-- Suggestions (only show when no messages) -->
    <div
      v-if="!chatStore.hasMessages"
      class="p-5 w-[70%] mx-auto"
      style="border-width: 0; background-color: transparent"
    >
      <SuggestionBubbles
        :suggestions="SUGGESTION_PROMPTS"
        @click="handleSuggestionClick"
      />
    </div>

    <!-- Input area -->
    <div
      class="p-5 w-[70%] mx-auto"
      style="border-width: 0"
    >
      <ChatInput
        v-model="chatStore.inputValue"
        :disabled="chatStore.isAiTyping"
        @send="handleSend"
      />
      <div class="text-center text-xs text-gray-500 mt-3">内容由AI生成，请仔细甄别</div>
    </div>
  </div>
</template>

<style scoped>
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
