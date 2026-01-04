<script setup lang="ts">
/**
 * ChatMessage - Individual chat message bubble with copy functionality
 */
import { computed } from 'vue'

import { CheckCheck, Copy } from 'lucide-vue-next'

import type { ChatMessage } from '@/stores'

const props = defineProps<{
  message: ChatMessage
  isCopied: boolean
}>()

const emit = defineEmits<{
  (e: 'copy', messageId: string): void
}>()

const isUser = computed(() => props.message.sender === 'user')

const formattedTime = computed(() => {
  return props.message.timestamp.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

// Avatar URLs
const userAvatarUrl =
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?ixlib=rb-1.2.1&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80'
const aiAvatarUrl =
  'https://space-static.coze.site/coze_space/7586606221064585514/upload/%E6%96%B0%E5%AF%B9%E8%AF%9D%281%29%281%29%281%29_536x662.png?sign=1768989628-231ab7c8de-0-26441aa331e9c26987be17f74685c0f95079054464622780e9f012aa077f9606'

function handleCopy() {
  emit('copy', props.message.id)
}
</script>

<template>
  <div
    class="chat-message flex"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="flex items-start space-x-3 max-w-[80%]"
      :class="isUser ? 'flex-row-reverse space-x-reverse' : ''"
    >
      <!-- Avatar -->
      <img
        :src="isUser ? userAvatarUrl : aiAvatarUrl"
        :alt="isUser ? '用户头像' : 'AI头像'"
        class="w-8 h-8 rounded-full object-cover mt-1 flex-shrink-0"
      />

      <!-- Content -->
      <div class="flex flex-col">
        <div
          class="px-4 py-3 rounded-lg shadow-sm"
          :class="
            isUser
              ? 'bg-blue-600 text-white rounded-br-none'
              : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
          "
        >
          <div class="whitespace-pre-wrap text-sm">{{ message.text }}</div>
        </div>

        <!-- Footer: time and copy -->
        <div class="flex items-center justify-between mt-1">
          <div
            class="text-xs text-gray-500"
            :class="isUser ? 'text-right' : 'text-left'"
          >
            {{ formattedTime }}
          </div>
          <button
            class="ml-2 p-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
            title="复制内容"
            @click="handleCopy"
          >
            <CheckCheck
              v-if="isCopied"
              class="w-3.5 h-3.5 text-green-500"
            />
            <Copy
              v-else
              class="w-3.5 h-3.5"
            />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
