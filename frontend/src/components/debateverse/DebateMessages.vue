<script setup lang="ts">
/**
 * DebateMessages - Speech bubbles for a specific side
 */
import { computed } from 'vue'

import { useDebateVerseStore } from '@/stores/debateverse'
import DebateMessage from './DebateMessage.vue'

const props = defineProps<{
  side: 'affirmative' | 'negative' | 'judge'
}>()

const store = useDebateVerseStore()

// ============================================================================
// Computed
// ============================================================================

const sideMessages = computed(() => {
  return store.messages.filter((msg) => {
    const participant = store.participants.find((p) => p.id === msg.participant_id)
    if (props.side === 'judge') {
      return participant?.role === 'judge'
    }
    return participant?.side === props.side
  })
})
</script>

<template>
  <div class="debate-messages flex flex-col gap-3 p-2 pb-4">
    <DebateMessage
      v-for="message in sideMessages"
      :key="message.id"
      :message="message"
    />
  </div>
</template>

<style scoped>
.debate-messages {
  min-height: 0;
  overflow-y: auto;
}
</style>
