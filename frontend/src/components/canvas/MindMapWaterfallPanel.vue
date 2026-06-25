<script setup lang="ts">
/**
 * Mind map waterfall panel — w-80 side tool shell with AI suggestions (panel-only, drag to canvas).
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { Loader2, RefreshCw, X } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { PALETTE_MINDMAP_DRAG_MIME } from '@/composables/nodePalette/constants'
import {
  beginMindMapPaletteDrag,
  endMindMapPaletteDrag,
  setEmptyNativeDragImage,
} from '@/composables/nodePalette/mindMapPaletteDragSession'
import { getNodePalette } from '@/composables/nodePalette/useNodePalette'
import { getLLMColor } from '@/config/llmModelColors'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const panelsStore = usePanelsStore()
const diagramStore = useDiagramStore()

const {
  isLoading,
  paletteStreamPhase,
  errorMessage,
  suggestions,
  selectedIds,
  mindMapSourceTabs,
  toggleSelection,
  dismiss,
  switchMindMapWaterfallTab,
  refreshMindMapWaterfall,
  startMindMapWaterfallSession,
} = getNodePalette({
  onError: (err) => notify.error(err),
})

const activeTabId = computed(() => panelsStore.nodePalettePanel.mode ?? 'topic')

const panelHint = computed(() => t('canvas.mindMapWaterfall.panelHint'))

const paletteTabStripGlowClass = computed(() => {
  if (!isLoading.value) return ''
  if (paletteStreamPhase.value === 'streaming') return 'waterfall-tab-strip--streaming'
  if (paletteStreamPhase.value === 'requesting') return 'waterfall-tab-strip--requesting'
  return 'waterfall-tab-strip--requesting'
})

function handleClose(): void {
  dismiss()
  emit('close')
}

async function handleRefresh(): Promise<void> {
  await refreshMindMapWaterfall()
}

function getNodeCardStyle(suggestion: { source_llm?: string }, isSelected: boolean) {
  const colors = suggestion.source_llm ? getLLMColor(suggestion.source_llm, uiStore.isDark) : null
  const selectedStyle = {
    borderColor: 'rgb(59, 130, 246)',
    backgroundColor: 'rgb(239, 246, 255)',
  }
  if (!colors) {
    return isSelected ? selectedStyle : {}
  }
  if (isSelected) {
    return {
      ...selectedStyle,
      borderLeftWidth: '4px',
      borderLeftStyle: 'solid',
      borderLeftColor: colors.text,
    }
  }
  return {
    borderColor: colors.border,
    backgroundColor: colors.bg,
  }
}

function handleDragStart(event: DragEvent, suggestion: NodeSuggestion): void {
  if (!event.dataTransfer) return
  const selected = selectedIds.value
  const tabSuggestions = suggestions.value
  const dragItems =
    selected.includes(suggestion.id) && selected.length > 1
      ? tabSuggestions.filter((s) => selected.includes(s.id))
      : [suggestion]
  const payload = {
    items: dragItems.map((s) => ({ id: s.id, text: s.text })),
  }
  event.dataTransfer.setData(PALETTE_MINDMAP_DRAG_MIME, JSON.stringify(payload))
  event.dataTransfer.effectAllowed = 'copy'
  setEmptyNativeDragImage(event)
  beginMindMapPaletteDrag({ items: payload.items })
}

function handleDragEnd(): void {
  endMindMapPaletteDrag()
}

const skipSelectionWatch = ref(true)

onMounted(async () => {
  panelsStore.updateNodePalette({ mindMapWaterfallMode: true })
  await nextTick()
  if (panelsStore.nodePalettePanel.suggestions.length === 0 && !isLoading.value) {
    await startMindMapWaterfallSession()
  }
  skipSelectionWatch.value = false
})

watch(
  () => [...diagramStore.selectedNodes],
  async (ids, prev) => {
    if (skipSelectionWatch.value || !prev) return
    if (ids.join(',') === prev.join(',')) return
    if (!panelsStore.nodePalettePanel.isOpen || !panelsStore.nodePalettePanel.mindMapWaterfallMode) {
      return
    }
    if (isLoading.value) return
    await startMindMapWaterfallSession()
  }
)
</script>

<template>
  <aside
    class="mind-map-waterfall-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.waterfall')"
  >
    <header class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 bg-gray-50/50 px-3 py-3">
      <h3 class="truncate text-sm font-semibold tracking-wide text-gray-800">
        {{ t('canvas.mindMapSideToolbar.waterfall') }}
      </h3>
      <div class="flex shrink-0 items-center gap-1">
        <button
          type="button"
          class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-all hover:bg-slate-100 hover:text-gray-600 disabled:opacity-40"
          :disabled="isLoading"
          :aria-label="t('nodePalette.refresh')"
          @click="handleRefresh"
        >
          <RefreshCw
            class="h-4 w-4"
            :class="{ 'animate-spin': isLoading }"
            :stroke-width="2"
          />
        </button>
        <button
          type="button"
          class="inline-flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 transition-all hover:bg-slate-100 hover:text-gray-600"
          :aria-label="t('canvas.mindMapSideToolbar.closePanel')"
          @click="handleClose"
        >
          <X
            class="h-4 w-4"
            :stroke-width="2"
          />
        </button>
      </div>
    </header>

    <p class="mind-map-waterfall-panel__hint shrink-0 border-b border-slate-100 px-3 py-2 text-[11px] leading-snug text-slate-500">
      {{ panelHint }}
    </p>

    <div
      v-if="mindMapSourceTabs.length > 1"
      class="shrink-0 border-b border-slate-100 px-2 py-2"
    >
      <div
        class="flex gap-1 overflow-x-auto"
        :class="paletteTabStripGlowClass"
      >
        <button
          v-for="tab in mindMapSourceTabs"
          :key="tab.id"
          type="button"
          class="shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors"
          :class="
            activeTabId === tab.id
              ? 'bg-blue-100 text-blue-800'
              : 'text-slate-600 hover:bg-slate-100'
          "
          @click="switchMindMapWaterfallTab(tab.id)"
        >
          {{ tab.name }}
        </button>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto px-3 py-3">
      <div
        v-if="isLoading && suggestions.length === 0"
        class="flex flex-col items-center justify-center gap-2 py-10 text-sm text-slate-500"
      >
        <Loader2 class="h-6 w-6 animate-spin text-blue-500" />
        <span>{{ t('nodePalette.generatingIdeas') }}</span>
      </div>

      <p
        v-else-if="errorMessage"
        class="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700"
      >
        {{ errorMessage }}
      </p>

      <div
        v-else-if="suggestions.length === 0"
        class="py-8 text-center text-xs text-slate-500"
      >
        {{ t('canvas.mindMapWaterfall.emptyHint') }}
      </div>

      <div
        v-else
        class="flex flex-col gap-2"
      >
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          draggable="true"
          class="waterfall-suggestion-card cursor-grab rounded-xl border border-slate-200 px-3 py-2.5 transition-shadow active:cursor-grabbing hover:shadow-sm"
          :class="{ 'ring-2 ring-blue-400 ring-offset-1': selectedIds.includes(suggestion.id) }"
          :style="getNodeCardStyle(suggestion, selectedIds.includes(suggestion.id))"
          @click="toggleSelection(suggestion.id)"
          @dragstart="handleDragStart($event, suggestion)"
          @dragend="handleDragEnd"
        >
          <span
            dir="auto"
            class="block text-sm leading-snug text-gray-800 line-clamp-3 break-words"
          >
            {{ suggestion.text }}
          </span>
        </div>
      </div>

      <p
        v-if="suggestions.length > 0"
        class="mt-3 rounded-lg bg-slate-50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-500"
      >
        {{ t('canvas.mindMapWaterfall.dragHint') }}
      </p>
    </div>
  </aside>
</template>

<style scoped>
.mind-map-waterfall-panel {
  max-height: calc(100% - 1.5rem);
}

.mind-map-waterfall-panel__hint {
  white-space: pre-line;
}

.waterfall-tab-strip--requesting {
  box-shadow: inset 0 -2px 0 rgb(59 130 246 / 0.45);
}

.waterfall-tab-strip--streaming {
  box-shadow: inset 0 -2px 0 rgb(34 197 94 / 0.55);
}

.waterfall-suggestion-card {
  user-select: none;
}
</style>
