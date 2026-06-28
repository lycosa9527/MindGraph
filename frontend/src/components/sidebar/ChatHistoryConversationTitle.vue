<script setup lang="ts">
import { Pin } from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { MindMateConversation } from '@/stores'

import MindMateDingtalkBadge from './MindMateDingtalkBadge.vue'

defineProps<{
  conv: MindMateConversation
  pinned?: boolean
}>()

const { t } = useLanguage()

function isMindbotConversation(conv: MindMateConversation): boolean {
  if (conv.channel === 'mindbot') {
    return true
  }
  return (conv.dify_user || '').startsWith('mindbot_')
}
</script>

<template>
  <span class="conv-name">
    <Pin
      v-if="pinned"
      class="w-3 h-3 inline-block mr-1 text-amber-500 shrink-0"
    />
    <span class="conv-name-text">
      {{ conv.name || t('sidebar.history.untitled') }}
    </span>
    <MindMateDingtalkBadge v-if="isMindbotConversation(conv)" />
  </span>
</template>

<style scoped>
.conv-name {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.conv-name-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
