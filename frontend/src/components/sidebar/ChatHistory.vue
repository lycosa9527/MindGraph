<script setup lang="ts">
/**
 * ChatHistory - List of recent chat conversations
 */
import { FileText } from 'lucide-vue-next'

// Mock history items
const historyItems = [
  { id: 1, title: '对话内容对话内容对话内容对话...' },
  { id: 2, title: '对话内容对话内容对话内容对话...' },
  { id: 3, title: '对话内容对话内容对话内容对话...' },
]
</script>

<template>
  <div class="chat-history p-4 border-t border-gray-200">
    <div class="text-xs font-medium text-gray-500 uppercase mb-3">历史对话</div>
    <div class="space-y-2">
      <button
        v-for="item in historyItems"
        :key="item.id"
        class="flex items-center w-full px-3 py-2.5 rounded-lg text-gray-600 hover:bg-gray-200 transition-colors"
      >
        <FileText class="w-4 h-4 mr-2 flex-shrink-0" />
        <span class="truncate text-sm">{{ item.title }}</span>
      </button>
    </div>
  </div>
</template>
