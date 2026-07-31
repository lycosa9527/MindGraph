<script setup lang="ts">
/**
 * MaiteLearningPage — thin shell for 迈特学习法 workspace.
 * Route: /maite
 */
import { onUnmounted } from 'vue'

import { MaiteWorkspace } from '@/components/maite'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

const store = useMaiteStore()

onUnmounted(() => {
  eventBus.emit('maite:session_closed', {
    sessionId: store.activeSessionId ?? undefined,
  })
  eventBus.emit('maite:mentor_stream_stop', {})
  store.resetWorkspace()
})
</script>

<template>
  <div class="maite-learning-page">
    <MaiteWorkspace />
  </div>
</template>

<style scoped>
.maite-learning-page {
  height: 100%;
  overflow: hidden;
}
</style>
