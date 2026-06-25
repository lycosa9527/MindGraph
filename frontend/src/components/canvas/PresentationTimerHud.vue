<script setup lang="ts">
/**
 * Compact presentation timer — bottom-right HUD while the presenter continues on canvas.
 */
import { Pause, Play, RotateCcw, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { PRESENTATION_Z } from '@/config/uiConfig'

defineProps<{
  remainingSeconds: number
  running: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleRun'): void
  (e: 'reset'): void
  (e: 'close'): void
}>()

const { t } = useLanguage()

function formatDisplay(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

const hudStyle = {
  zIndex: PRESENTATION_Z.TIMER_OVERLAY - 1,
} as const
</script>

<template>
  <div
    class="presentation-timer-hud pointer-events-auto fixed bottom-4 right-4 flex items-center gap-2 rounded-2xl border border-gray-200/80 bg-white/92 px-3 py-2 shadow-xl backdrop-blur-md dark:border-gray-600/80 dark:bg-gray-900/88 sm:bottom-6 sm:right-6"
      :style="hudStyle"
      role="status"
      :aria-label="t('canvas.presentationTimer.title')"
    >
      <span
        class="min-w-[4.5rem] font-mono text-xl font-bold tabular-nums tracking-tight text-gray-900 dark:text-gray-100"
        :class="{ 'text-red-600 dark:text-red-400': remainingSeconds <= 60 && remainingSeconds > 0 }"
      >
        {{ formatDisplay(remainingSeconds) }}
      </span>

      <div class="mx-0.5 h-5 w-px bg-gray-200 dark:bg-gray-600" />

      <button
        type="button"
        class="timer-hud-btn"
        :aria-label="running ? t('canvas.presentationTimer.pause') : t('canvas.presentationTimer.start')"
        @click="emit('toggleRun')"
      >
        <Pause
          v-if="running"
          class="h-4 w-4"
        />
        <Play
          v-else
          class="h-4 w-4"
        />
      </button>

      <button
        type="button"
        class="timer-hud-btn"
        :aria-label="t('canvas.presentationTimer.reset')"
        @click="emit('reset')"
      >
        <RotateCcw class="h-4 w-4" />
      </button>

      <button
        type="button"
        class="timer-hud-btn timer-hud-btn--close"
        :aria-label="t('canvas.presentationTimer.closeHud')"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
  </div>
</template>

<style scoped>
.timer-hud-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 0.625rem;
  background: transparent;
  color: rgb(55 65 81);
  cursor: pointer;
}

.timer-hud-btn:hover {
  background: rgb(243 244 246);
}

.timer-hud-btn--close:hover {
  background: rgb(254 226 226);
  color: rgb(185 28 28);
}

.dark .timer-hud-btn {
  color: rgb(229 231 235);
}

.dark .timer-hud-btn:hover {
  background: rgb(75 85 99);
}

.dark .timer-hud-btn--close:hover {
  background: rgb(127 29 29 / 0.45);
  color: rgb(248 113 113);
}
</style>
