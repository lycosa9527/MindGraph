<script setup lang="ts">
/**
 * Collapsible canvas multi-touch guide — sits next to the shortcut guide.
 */
import { computed, onMounted, ref } from 'vue'

import { ChevronDown, ChevronUp, Hand } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import {
  activeCanvasGuideId,
  openCanvasGuide,
  toggleCanvasGuide,
} from '@/composables/canvas/canvasGuideExclusive'
import { MIND_MAP_GESTURE_GUIDE_ROWS } from '@/config/mindMapGestureGuide'

const STORAGE_KEY = 'mindgraph.mindmap.gestureGuide.expanded'

const props = withDefaults(
  defineProps<{
    variant?: 'floating' | 'status'
  }>(),
  { variant: 'floating' }
)

const { t } = useLanguage()

const expandedLocal = ref(false)
const isStatus = computed(() => props.variant === 'status')

const expanded = computed(() =>
  isStatus.value ? activeCanvasGuideId.value === 'gesture' : expandedLocal.value
)

onMounted(() => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'true') {
      if (isStatus.value) {
        openCanvasGuide('gesture')
      } else {
        expandedLocal.value = true
      }
    }
  } catch {
    /* ignore private mode */
  }
})

function persistExpanded(next: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(next))
  } catch {
    /* ignore */
  }
}

function toggleExpanded(): void {
  if (isStatus.value) {
    persistExpanded(toggleCanvasGuide('gesture'))
    return
  }
  expandedLocal.value = !expandedLocal.value
  persistExpanded(expandedLocal.value)
}
</script>

<template>
  <div
    class="select-none shrink-0"
    :class="{ 'gesture-guide--status': isStatus }"
  >
    <button
      v-if="isStatus"
      type="button"
      class="mm-status__zoom-btn"
      :class="{ 'is-active': expanded }"
      :aria-expanded="expanded"
      :aria-label="t('canvas.gestureGuide.title')"
      :title="t('canvas.gestureGuide.title')"
      @click="toggleExpanded"
    >
      <I18nText k="canvas.gestureGuide.shortLabel" />
      <Hand
        class="h-3.5 w-3.5"
        :stroke-width="2"
      />
    </button>
    <button
      v-else-if="!expanded"
      type="button"
      class="inline-flex items-center gap-2 rounded-xl border border-gray-200/80 bg-white/90 px-3 py-2 text-xs font-semibold text-slate-700 shadow-lg backdrop-blur-md transition-all hover:border-slate-300 hover:bg-white dark:border-gray-600/80 dark:bg-gray-800/90 dark:text-slate-200 dark:hover:bg-gray-800"
      :aria-expanded="false"
      :aria-label="t('canvas.gestureGuide.title')"
      @click="toggleExpanded"
    >
      <Hand
        class="shrink-0 text-teal-500"
        :size="15"
        :stroke-width="2"
      />
      <span class="whitespace-nowrap">{{ t('canvas.gestureGuide.title') }}</span>
      <ChevronUp
        class="shrink-0 text-slate-400"
        :size="14"
        :stroke-width="2"
      />
    </button>

    <Transition name="gesture-guide-card">
      <div
        v-if="expanded"
        class="gesture-guide-card w-60 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-600 dark:bg-gray-900"
        :class="{ 'gesture-guide-card--popover': isStatus }"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-slate-100 px-3 pb-1 pt-2 dark:border-slate-700"
        >
          <div class="flex min-w-0 items-center gap-2">
            <Hand
              class="shrink-0 text-teal-500"
              :size="15"
              :stroke-width="2"
            />
            <span class="truncate text-xs font-bold text-slate-800 dark:text-slate-100">
              {{ t('canvas.gestureGuide.title') }}
            </span>
          </div>
          <button
            type="button"
            class="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200/80 bg-slate-50 text-slate-500 transition-colors hover:border-slate-300 hover:bg-white hover:text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-400"
            :aria-label="t('canvas.gestureGuide.collapse')"
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
            v-for="row in MIND_MAP_GESTURE_GUIDE_ROWS"
            :key="row.id"
            class="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50/80 px-2 py-1.5 dark:border-slate-700/80 dark:bg-slate-800/60"
          >
            <span class="text-xs text-slate-700 dark:text-slate-200">
              {{ t(row.labelKey) }}
            </span>
            <span
              class="max-w-[52%] shrink-0 text-right text-[10px] leading-tight text-slate-500 dark:text-slate-400"
            >
              {{ t(row.hintKey) }}
            </span>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.gesture-guide--status {
  position: relative;
}

.gesture-guide-card--popover {
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 60;
}

.gesture-guide-card-enter-active,
.gesture-guide-card-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.22s ease;
  transform-origin: bottom left;
}

.gesture-guide-card--popover.gesture-guide-card-enter-active,
.gesture-guide-card--popover.gesture-guide-card-leave-active {
  transform-origin: bottom right;
}

.gesture-guide-card-enter-from,
.gesture-guide-card-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.gesture-guide-card-enter-to,
.gesture-guide-card-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}
</style>
