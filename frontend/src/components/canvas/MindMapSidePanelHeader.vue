<script setup lang="ts">
/**
 * Shared side-rail panel header: title + smaller grey instruction under it.
 */
import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'

defineProps<{
  title: string
  intro?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

function handleClose(): void {
  emit('close')
}
</script>

<template>
  <header class="mind-map-side-panel-header shrink-0 border-b border-(--swiss-border,#e7e5e4) px-3 py-3">
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0 flex-1">
        <h3 class="truncate text-base font-semibold leading-snug text-(--swiss-ink,#1c1917)">
          {{ title }}
        </h3>
        <p
          v-if="intro"
          class="mind-map-side-panel-header__intro mt-0.5 text-xs leading-snug text-(--swiss-muted,#78716c)"
        >
          {{ intro }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-1">
        <slot name="actions" />
        <MindMapSidePanelCloseButton @close="handleClose" />
      </div>
    </div>
    <div
      v-if="$slots.below"
      class="mt-2"
    >
      <slot name="below" />
    </div>
  </header>
</template>
