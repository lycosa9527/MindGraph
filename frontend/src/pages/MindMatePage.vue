<script setup lang="ts">
/**
 * MindMatePage - Full-page MindMate chat interface
 * Route: /mindmate
 */
import { MindmatePanel } from '@/components/panels'
</script>

<template>
  <div class="mindmate-page flex-1 flex flex-col bg-white">
    <MindmatePanel
      mode="fullpage"
      class="flex-1"
    />
  </div>
</template>
