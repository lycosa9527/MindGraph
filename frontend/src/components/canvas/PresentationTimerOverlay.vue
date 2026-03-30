<script setup lang="ts">
/**
 * Dim overlay with a large countdown timer for presentation.
 * Teleported to `body` with z-index from PRESENTATION_Z so it sits above canvas chrome
 * and is not clipped by layout overflow. Wall clock is rendered inside this layer.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { LogOut, Pause, Play, RotateCcw } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { PRESENTATION_Z } from '@/config/uiConfig'
import { intlLocaleForUiCode } from '@/i18n'
import type { LocaleCode } from '@/i18n/locales'

defineProps<{
  remainingSeconds: number
  totalSeconds: number
  running: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleRun'): void
  (e: 'reset'): void
  (e: 'exit'): void
  (e: 'presetMinutes', minutes: number): void
  (e: 'setMinutes', minutes: number): void
}>()

const { t, currentLanguage } = useLanguage()

const customMinutes = ref(5)

const PRESETS = [1, 3, 5, 10, 15] as const

const wallClockText = ref('')
let wallClockIntervalId: ReturnType<typeof setInterval> | null = null

function updateWallClock(): void {
  wallClockText.value = new Date().toLocaleTimeString(
    intlLocaleForUiCode(currentLanguage.value as LocaleCode),
    { hour: '2-digit', minute: '2-digit', second: '2-digit' }
  )
}

function stopWallClock(): void {
  if (wallClockIntervalId !== null) {
    clearInterval(wallClockIntervalId)
    wallClockIntervalId = null
  }
}

onMounted(() => {
  updateWallClock()
  wallClockIntervalId = window.setInterval(updateWallClock, 1000)
})

onUnmounted(() => {
  stopWallClock()
})

watch(currentLanguage, () => {
  updateWallClock()
})

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

function applyCustom(): void {
  const m = Math.min(180, Math.max(1, Math.round(customMinutes.value)))
  customMinutes.value = m
  emit('setMinutes', m)
}

const overlayStyle = {
  zIndex: PRESENTATION_Z.TIMER_OVERLAY,
} as const
</script>

<template>
  <Teleport to="body">
    <div
      class="presentation-timer-overlay pointer-events-auto fixed inset-0 box-border overflow-x-hidden overflow-y-auto overscroll-y-contain bg-black/75"
      role="dialog"
      :style="overlayStyle"
      :aria-label="t('canvas.presentationTimer.title')"
    >
      <div
        class="flex min-h-[100dvh] w-full flex-col items-center justify-center gap-6 px-3 py-6 sm:gap-8 sm:px-4 sm:py-8"
      >
        <div
          class="presentation-timer-display pointer-events-none w-full max-w-[min(100vw-1.5rem,72rem)] shrink-0 px-1 text-center font-mono font-bold tabular-nums leading-none tracking-tight text-white drop-shadow-lg"
        >
          {{ formatDisplay(remainingSeconds) }}
        </div>

        <div class="flex w-full max-w-xl shrink-0 flex-wrap justify-center gap-2">
          <ElButton
            v-for="m in PRESETS"
            :key="m"
            native-type="button"
            size="small"
            round
            @click.stop="emit('presetMinutes', m)"
          >
            {{ m }}{{ t('canvas.presentationTimer.minSuffix') }}
          </ElButton>
        </div>

        <div class="flex w-full max-w-xl shrink-0 flex-wrap items-center justify-center gap-2">
          <label class="flex items-center gap-2 text-sm text-white/90">
            <span>{{ t('canvas.presentationTimer.customMinutes') }}</span>
            <input
              v-model.number="customMinutes"
              type="number"
              min="1"
              max="180"
              class="w-20 rounded-md border border-white/30 bg-white/10 px-2 py-1 text-center text-white"
              @keydown.enter.prevent="applyCustom"
            />
          </label>
          <ElButton
            native-type="button"
            size="small"
            @click.stop="applyCustom"
          >
            {{ t('canvas.presentationTimer.set') }}
          </ElButton>
        </div>

        <div class="flex w-full max-w-2xl shrink-0 flex-wrap items-center justify-center gap-3">
          <ElButton
            type="primary"
            size="large"
            round
            @click.stop="emit('toggleRun')"
          >
            <Play
              v-if="!running"
              class="mr-1 h-5 w-5"
            />
            <Pause
              v-else
              class="mr-1 h-5 w-5"
            />
            {{ running ? t('canvas.presentationTimer.pause') : t('canvas.presentationTimer.start') }}
          </ElButton>
          <ElButton
            native-type="button"
            size="large"
            round
            @click.stop="emit('reset')"
          >
            <RotateCcw class="mr-1 h-5 w-5" />
            {{ t('canvas.presentationTimer.reset') }}
          </ElButton>
          <ElButton
            native-type="button"
            size="large"
            round
            @click.stop="emit('exit')"
          >
            <LogOut class="mr-1 h-5 w-5" />
            {{ t('canvas.presentationTimer.exitTimer') }}
          </ElButton>
        </div>

        <div
          class="pointer-events-none absolute bottom-3 right-3 rounded-md border border-white/25 bg-black/45 px-2.5 py-1 font-mono text-xs tabular-nums text-white/95 shadow-sm backdrop-blur-sm sm:bottom-4 sm:right-4"
          role="status"
          aria-live="polite"
        >
          {{ wallClockText }}
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.presentation-timer-display {
  line-height: 1.05;
  text-align: center;
  max-width: 100%;
  /*
   * Viewport-relative size (adaptive to window resize):
   * - min(…vmin, …vw): follow the smaller of “% of shorter viewport side” and “% of width”
   * - clamp: floor for tiny viewports, ceiling so the row + controls still fit
   */
  font-size: clamp(2.25rem, min(48vmin, 42vw), min(62vh, 68dvh));
}
</style>
