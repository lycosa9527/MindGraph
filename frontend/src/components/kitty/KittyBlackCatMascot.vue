<script setup lang="ts">
/**
 * Animated SVG Kitty mascot (same asset as utils/mascot/blackCat.ts) for mobile Kitty landing.
 */
import { onMounted, onUnmounted, useTemplateRef, watch } from 'vue'

import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'
import { BlackCat, type KittyState } from '@/utils/mascot/blackCat'

const props = defineProps<{
  agentState: KittyAgentState
}>()

const hostRef = useTemplateRef<HTMLDivElement>('hostRef')

let mascot: BlackCat | null = null

function mapAgentToMascot(state: KittyAgentState): KittyState {
  switch (state) {
    case 'listening':
      return 'listening'
    case 'speaking':
      return 'speaking'
    case 'connecting':
      return 'thinking'
    case 'error':
      return 'error'
    case 'active':
      return 'idle'
    default:
      return 'idle'
  }
}

function syncState(): void {
  if (mascot) {
    mascot.setState(mapAgentToMascot(props.agentState))
  }
}

onMounted(() => {
  const el = hostRef.value
  if (!el) return
  mascot = new BlackCat()
  mascot.init(el)
  syncState()
})

watch(
  () => props.agentState,
  () => {
    syncState()
  }
)

onUnmounted(() => {
  mascot?.destroy()
  mascot = null
})
</script>

<template>
  <div
    ref="hostRef"
    class="kitty-black-cat-mascot flex items-end justify-center mx-auto w-[min(200px,55vw)] aspect-[200/300] max-h-[min(240px,38vh)]"
    aria-hidden="true"
  />
</template>

<style scoped>
.kitty-black-cat-mascot :deep(.black-cat-container) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.kitty-black-cat-mascot :deep(.black-cat-container .kitty-svg) {
  max-height: 100%;
  width: auto;
}
</style>
