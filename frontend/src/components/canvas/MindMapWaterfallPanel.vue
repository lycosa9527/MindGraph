<script setup lang="ts">
/**
 * Side-tool entry for mind-map AI Brainstorm (legacy waterfall tool id).
 */
import AiBrainstormPanel from '@/components/canvas/AiBrainstormPanel.vue'

const emit = defineEmits<{
  (e: 'close'): void
}>()

function handleClose(): void {
  emit('close')
}
</script>

<template>
  <AiBrainstormPanel @close="handleClose" />
</template>
