<script setup lang="ts">
/**
 * Developer workflow trace panel (speech → hub → canvas); shown when paired with mobile Kitty.
 */
import { computed } from 'vue'

import type { KittyDesktopWorkflowEntry } from '@/composables/kitty/useKittyDesktopWorkflowDebug'
import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  visible: boolean
  entries: KittyDesktopWorkflowEntry[]
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
  <Transition name="kitty-wf-log-pop">
    <aside
      v-if="visible && hasEntries"
      class="kitty-wf-log pointer-events-none fixed z-[58] w-[min(22rem,calc(100vw-5rem))] select-none"
      :style="{
        left: 'max(12px, env(safe-area-inset-left))',
        bottom: 'calc(max(12px, env(safe-area-inset-bottom)) + 12.5rem)',
      }"
      role="log"
      :aria-label="t('canvas.kittyWorkflowDebugAria')"
    >
      <div
        class="rounded-xl border border-slate-300/80 bg-slate-50/95 shadow-lg backdrop-blur-sm dark:border-slate-600/50 dark:bg-slate-900/95"
      >
        <div
          class="border-b border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 dark:border-slate-600/40 dark:text-slate-200"
        >
          {{ t('canvas.kittyWorkflowDebugTitle') }}
        </div>
        <ul class="max-h-52 overflow-hidden px-2 py-1.5 font-mono text-[10px] leading-snug">
          <li
            v-for="row in entries"
            :key="row.id"
            class="flex items-start gap-2 py-0.5"
          >
            <span
              class="mt-px shrink-0 text-slate-400 dark:text-slate-500"
              aria-hidden="true"
            >
              {{ formatTime(row.at) }}
            </span>
            <span class="shrink-0 text-violet-600 dark:text-violet-400">
              {{ row.lane }}/{{ row.stage }}
            </span>
            <span class="min-w-0 flex-1 break-all text-slate-800 dark:text-slate-100">
              {{ row.detail }}
            </span>
          </li>
        </ul>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.kitty-wf-log-pop-enter-active {
  transition:
    transform 0.28s cubic-bezier(0.34, 1.45, 0.64, 1),
    opacity 0.22s ease-out;
}

.kitty-wf-log-pop-leave-active {
  transition:
    transform 0.18s ease-in,
    opacity 0.16s ease-in;
}

.kitty-wf-log-pop-enter-from {
  transform: translateY(10px) scale(0.96);
  opacity: 0;
}

.kitty-wf-log-pop-leave-to {
  transform: translateY(6px) scale(0.98);
  opacity: 0;
}
</style>
