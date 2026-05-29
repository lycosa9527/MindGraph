<script setup lang="ts">
/**
 * Floating panel above the mobile Kitty FAB showing recent voice commands from phone.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import type { KittyDesktopVoiceCommandEntry } from '@/composables/kitty/useKittyDesktopVoiceCommandLog'

const props = defineProps<{
  visible: boolean
  entries: KittyDesktopVoiceCommandEntry[]
}>()

const { t } = useLanguage()

const hasEntries = computed(() => props.entries.length > 0)

function formatTime(at: number): string {
  const d = new Date(at)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
</script>

<template>
  <Transition name="kitty-voice-log-pop">
    <aside
      v-if="visible && hasEntries"
      class="kitty-voice-log pointer-events-none fixed z-[59] w-[min(17rem,calc(100vw-5rem))] select-none"
      :style="{
        left: 'max(12px, env(safe-area-inset-left))',
        bottom: 'calc(max(12px, env(safe-area-inset-bottom)) + 4.5rem)',
      }"
      role="log"
      :aria-label="t('canvas.kittyVoiceCommandLogAria')"
    >
      <div
        class="rounded-xl border border-violet-200/80 bg-white/95 shadow-lg backdrop-blur-sm dark:border-violet-500/40 dark:bg-gray-900/95"
      >
        <div
          class="border-b border-violet-100 px-3 py-2 text-xs font-semibold text-violet-700 dark:border-violet-500/30 dark:text-violet-300"
        >
          {{ t('canvas.kittyVoiceCommandLogTitle') }}
        </div>
        <ul class="max-h-40 overflow-hidden px-2 py-1.5">
          <li
            v-for="row in entries"
            :key="row.id"
            class="flex items-start gap-2 py-1 text-xs leading-snug"
          >
            <span
              class="mt-0.5 shrink-0 font-mono text-[10px] text-gray-400 dark:text-gray-500"
              aria-hidden="true"
            >
              {{ formatTime(row.at) }}
            </span>
            <span class="min-w-0 flex-1 text-gray-800 dark:text-gray-100">
              {{ row.label }}
            </span>
          </li>
        </ul>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.kitty-voice-log-pop-enter-active {
  transition:
    transform 0.28s cubic-bezier(0.34, 1.45, 0.64, 1),
    opacity 0.22s ease-out;
}

.kitty-voice-log-pop-leave-active {
  transition:
    transform 0.18s ease-in,
    opacity 0.16s ease-in;
}

.kitty-voice-log-pop-enter-from {
  transform: translateY(10px) scale(0.96);
  opacity: 0;
}

.kitty-voice-log-pop-leave-to {
  transform: translateY(6px) scale(0.98);
  opacity: 0;
}
</style>
