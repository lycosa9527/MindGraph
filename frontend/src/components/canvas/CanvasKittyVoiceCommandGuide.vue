<script setup lang="ts">
/**
 * Collapsible Kitty voice-command guide — same style as mind-map shortcut guide.
 */
import { computed, onMounted, ref } from 'vue'

import { ChevronDown, ChevronUp, Mic } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { formatKittyVoiceCommandLabel } from '@/composables/kitty/kittyVoiceCommandLabels'
import { KITTY_VOICE_COMMAND_GUIDE_ROWS } from '@/config/kittyVoiceCommandGuide'

const STORAGE_KEY = 'mindgraph.kitty.voiceCommandGuide.expanded'

const { t } = useLanguage()

const expanded = ref(true)

const rows = computed(() =>
  KITTY_VOICE_COMMAND_GUIDE_ROWS.map((row) => {
    const raw = formatKittyVoiceCommandLabel(row.action, undefined, (key, params) =>
      t(key, params ?? {})
    )
    return {
      id: row.id,
      label: raw.replace(/[：:]\s*$/u, '').trim() || raw,
      example: t(row.exampleKey),
    }
  })
)

onMounted(() => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored !== null) {
      expanded.value = stored === 'true'
    }
  } catch {
    /* ignore private mode */
  }
})

function toggleExpanded(): void {
  expanded.value = !expanded.value
  try {
    localStorage.setItem(STORAGE_KEY, String(expanded.value))
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div class="select-none shrink-0">
    <button
      v-if="!expanded"
      type="button"
      class="inline-flex items-center gap-2 rounded-xl border border-violet-200/80 bg-white/90 dark:border-violet-500/40 dark:bg-gray-800/90 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 shadow-lg backdrop-blur-md transition-all hover:border-violet-300 hover:bg-white dark:hover:bg-gray-800"
      :aria-expanded="false"
      :aria-label="t('canvas.voiceCommandGuide.title')"
      @click="toggleExpanded"
    >
      <Mic
        class="shrink-0 text-violet-500"
        :size="15"
        :stroke-width="2"
      />
      <span class="whitespace-nowrap">{{ t('canvas.voiceCommandGuide.title') }}</span>
      <ChevronUp
        class="shrink-0 text-slate-400"
        :size="14"
        :stroke-width="2"
      />
    </button>

    <Transition name="voice-command-guide-card">
      <div
        v-if="expanded"
        class="voice-command-guide-card w-60 overflow-hidden rounded-xl border border-violet-200/80 bg-white shadow-lg dark:border-violet-500/40 dark:bg-gray-900"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-violet-100 px-3 pb-1 pt-2 dark:border-violet-500/30"
        >
          <div class="flex min-w-0 items-center gap-2">
            <Mic
              class="shrink-0 text-violet-500"
              :size="15"
              :stroke-width="2"
            />
            <span class="truncate text-xs font-bold text-slate-800 dark:text-slate-100">
              {{ t('canvas.voiceCommandGuide.title') }}
            </span>
          </div>
          <button
            type="button"
            class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200/80 bg-slate-50 text-slate-500 transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400"
            :aria-label="t('canvas.voiceCommandGuide.collapse')"
            @click="toggleExpanded"
          >
            <ChevronDown
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <ul class="flex max-h-[min(50vh,17.5rem)] flex-col gap-1 overflow-y-auto px-2 pb-1.5 pt-0">
          <li
            v-for="row in rows"
            :key="row.id"
            class="flex flex-col gap-0.5 rounded-md border border-violet-50 bg-violet-50/60 px-2 py-1.5 dark:border-violet-900/50 dark:bg-violet-950/30"
          >
            <span class="text-xs font-medium text-slate-700 dark:text-slate-200">
              {{ row.label }}
            </span>
            <span class="text-[10px] leading-snug text-slate-500 dark:text-slate-400">
              {{ row.example }}
            </span>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.voice-command-guide-card-enter-active,
.voice-command-guide-card-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.22s ease;
  transform-origin: bottom left;
}

.voice-command-guide-card-enter-from,
.voice-command-guide-card-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.voice-command-guide-card-enter-to,
.voice-command-guide-card-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
</style>
