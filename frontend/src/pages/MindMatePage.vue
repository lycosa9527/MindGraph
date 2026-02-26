<script setup lang="ts">
/**
 * MindMatePage - Full-page MindMate chat interface
 * Route: /mindmate
 */
import { onUnmounted } from 'vue'

import { MindmatePanel } from '@/components/panels'
import { useVoiceStore } from '@/stores'

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
