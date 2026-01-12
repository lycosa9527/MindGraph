<script setup lang="ts">
/**
 * DebateMessages - Speech bubbles for debate messages
 * Shows all messages in chatroom style when side='all', or filtered by side
 */
import { computed, nextTick, onMounted, onUpdated, ref, watch } from 'vue'

import { useDebateVerseStore } from '@/stores/debateverse'
import DebateMessage from './DebateMessage.vue'

const props = defineProps<{
  side: 'affirmative' | 'negative' | 'judge' | 'all'
}>()

const store = useDebateVerseStore()
const messagesContainer = ref<HTMLElement | null>(null)

// ============================================================================
// Computed
// ============================================================================

const sideMessages = computed(() => {
  const allMessages = [...store.messages]
  
  // Add streaming message if exists
  if (store.streamingMessage) {
    allMessages.push(store.streamingMessage as any)
  }
  
  if (props.side === 'all') {
    // Show all messages sorted by creation time
    return allMessages.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime()
      const dateB = new Date(b.created_at).getTime()
      return dateA - dateB
    })
  }

  return allMessages.filter((msg) => {
    const participant = store.participants.find((p) => p.id === msg.participant_id)
    if (props.side === 'judge') {
      return participant?.role === 'judge'
    }
    return participant?.side === props.side
  })
})

// ============================================================================
// Auto-scroll to bottom
// ============================================================================

function scrollToBottom() {
  nextTick(() => {
    if (!messagesContainer.value) return
    
    // Try multiple selectors to find scrollable element
    const scrollbarWrap = messagesContainer.value.closest('.el-scrollbar__wrap')
    if (scrollbarWrap) {
      scrollbarWrap.scrollTop = scrollbarWrap.scrollHeight
      return
    }
    
    // Fallback: find scrollbar in parent chain
    let parent = messagesContainer.value.parentElement
    while (parent) {
      const wrap = parent.querySelector('.el-scrollbar__wrap')
      if (wrap) {
        wrap.scrollTop = wrap.scrollHeight
        return
      }
      parent = parent.parentElement
    }
    
    // Final fallback: direct scroll
    if (messagesContainer.value.scrollTop !== undefined) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

onMounted(() => {
  scrollToBottom()
})

onUpdated(() => {
  scrollToBottom()
})

// Watch for streaming updates and messages changes
watch(() => [store.streamingMessage, store.messages], () => {
  scrollToBottom()
}, { deep: true })
</script>

<template>
  <div
    ref="messagesContainer"
    class="debate-messages flex flex-col gap-4"
  >
    <DebateMessage
      v-for="(message, index) in sideMessages"
      :key="message.id || `streaming-${index}`"
      :message="message"
    />
  </div>
</template>

<style scoped>
.debate-messages {
  min-height: 0;
}
</style>
