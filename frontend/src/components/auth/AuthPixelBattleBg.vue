<script setup lang="ts">
/**
 * Retro pixel battle background for /auth — gated by FEATURE_AUTH_PIXEL_BATTLE.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { initAuthPixelBattle } from '@/utils/mascot/authPixelBattle'

const canvasRef = ref<HTMLCanvasElement | null>(null)
let dispose: (() => void) | null = null

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) {
    return
  }
  dispose = initAuthPixelBattle(canvas, { showHud: false })
})

onBeforeUnmount(() => {
  dispose?.()
  dispose = null
})
</script>

<template>
  <canvas
    ref="canvasRef"
    class="auth-pixel-battle-bg"
    aria-hidden="true"
  />
</template>

<style scoped>
.auth-pixel-battle-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  object-fit: cover;
}

@media (prefers-reduced-motion: reduce) {
  .auth-pixel-battle-bg {
    opacity: 0.85;
  }
}
</style>
