<script setup lang="ts">
import { computed } from 'vue'

import { ElButton, ElDrawer, ElIcon } from 'element-plus'

import { Delete, DocumentCopy } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import { type MindMateConversation, useMindMateStore } from '@/stores'

const props = defineProps<{
  visible: boolean
  conversations: MindMateConversation[]
  isLoading: boolean
  currentConversationId: string | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'load', conversationId: string): void
  (e: 'delete', conversationId: string): void
}>()

const { isZh } = useLanguage()
const _mindMateStore = useMindMateStore()

const showHistory = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

function formatConversationDate(timestamp: number): string {
  const date = new Date(timestamp * 1000) // Dify uses seconds
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return isZh.value ? '今天' : 'Today'
  } else if (diffDays === 1) {
    return isZh.value ? '昨天' : 'Yesterday'
  } else if (diffDays < 7) {
    return isZh.value ? `${diffDays}天前` : `${diffDays} days ago`
  } else {
    return date.toLocaleDateString(isZh.value ? 'zh-CN' : 'en-US', {
      month: 'short',
      day: 'numeric',
    })
  }
}

function handleLoad(conversationId: string) {
  emit('load', conversationId)
  showHistory.value = false
}

function handleDelete(conversationId: string, event: Event) {
  event.stopPropagation()
  emit('delete', conversationId)
}
</script>

<template>
  <ElDrawer
    v-model="showHistory"
    :title="isZh ? '历史会话' : 'Conversation History'"
    direction="ltr"
    size="280px"
    :with-header="true"
    :modal="true"
    :append-to-body="true"
    class="history-drawer"
  >
    <div class="conversation-list">
      <!-- Loading State -->
      <div
        v-if="isLoading"
        class="text-center py-8 text-gray-500"
      >
        <div
          class="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-2"
        />
        <span class="text-sm">{{ isZh ? '加载中...' : 'Loading...' }}</span>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="conversations.length === 0"
        class="text-center py-8 text-gray-500"
      >
        <ElIcon class="text-4xl mb-2 text-gray-300"><DocumentCopy /></ElIcon>
        <p class="text-sm">{{ isZh ? '暂无历史会话' : 'No conversation history' }}</p>
      </div>

      <!-- Conversation List -->
      <div
        v-else
        class="space-y-1"
      >
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conversation-item p-3 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors group"
          :class="{
            'bg-primary-50 dark:bg-primary-900/30': currentConversationId === conv.id,
          }"
          @click="handleLoad(conv.id)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-800 dark:text-white truncate">
                {{ conv.name || (isZh ? '未命名会话' : 'Untitled') }}
              </p>
              <p class="text-xs text-gray-500 mt-0.5">
                {{ formatConversationDate(conv.updated_at) }}
              </p>
            </div>
            <ElButton
              text
              size="small"
              class="opacity-0 group-hover:opacity-100 transition-opacity"
              @click="handleDelete(conv.id, $event)"
            >
              <ElIcon class="text-gray-400 hover:text-red-500"><Delete /></ElIcon>
            </ElButton>
          </div>
        </div>
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped>
@import './mindmate.css';
</style>
