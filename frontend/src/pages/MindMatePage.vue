<script setup lang="ts">
/**
 * MindMatePage - Full-page MindMate chat interface
 * Route: /mindmate
 */
import { onMounted, onUnmounted } from 'vue'

import { MindmatePanel } from '@/components/panels'
import { ensureMarkdownRenderer } from '@/composables/core/useMarkdown'
import { useAuthStore, useVoiceStore } from '@/stores'

const authStore = useAuthStore()

onMounted(() => {
  void ensureMarkdownRenderer()
  void authStore.checkAuth(true)
})

onUnmounted(() => {
  useVoiceStore().reset()
})
</script>

<template>
  <div class="mindmate-page flex-1 flex flex-col bg-white">
    <MindmatePanel
      mode="fullpage"
      class="flex-1"
    />
  </div>
</template>
