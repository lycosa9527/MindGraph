<script setup lang="ts">
/**
 * AI Brainstorm (AI头脑风暴) — mind-map side panel for new Canvas.
 * Own module UI: staged tabs, panel multi-select, Next/Finish, load more, drag-to-canvas.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { Check, Loader2, RefreshCw } from '@lucide/vue'

import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'

import { useLanguage, useNotifications } from '@/composables'
import { getAiBrainstorm } from '@/composables/aiBrainstorm/useAiBrainstorm'
import { PALETTE_MINDMAP_DRAG_MIME } from '@/composables/nodePalette/constants'
import {
  beginMindMapPaletteDrag,
  endMindMapPaletteDrag,
  setEmptyNativeDragImage,
} from '@/composables/nodePalette/mindMapPaletteDragSession'
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
  isLoadingMore,
  paletteStreamPhase,
  errorMessage,
  suggestions,
  selectedIds,
  sourceTabs,
  showNextButton,
  showStage2Tabs,
  stage2Parents,
  sessionId,
  toggleSelection,
  switchTab,
  switchStageTab,
  refreshSession,
  startSession,
  loadNextBatch,
  finishSelection,
  cancel,
  dismiss,
} = getAiBrainstorm({
  onError: (err) => notify.error(err),
})

const activeTabId = computed(() => panelsStore.aiBrainstormPanel.mode ?? 'topic')

const paletteTabStripGlowClass = computed(() => {
  if (!isLoading.value && !isLoadingMore.value) return ''
  if (paletteStreamPhase.value === 'streaming') return 'brainstorm-tab-strip--streaming'
  if (paletteStreamPhase.value === 'requesting') return 'brainstorm-tab-strip--requesting'
  return 'brainstorm-tab-strip--requesting'
})

const showTabs = computed(
  () => showStage2Tabs.value || sourceTabs.value.length > 1
)

function handleClose(): void {
  dismiss()
  emit('close')
}

async function handleRefresh(): Promise<void> {
  await refreshSession()
}

async function handleFinish(): Promise<void> {
  const closed = await finishSelection()
  if (closed) emit('close')
}

function handleCancel(): void {
  cancel()
  emit('close')
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

async function handleStageTab(parentId: string, parentName: string): Promise<void> {
  await switchStageTab(parentId, parentName)
}

const skipSelectionWatch = ref(true)
let stopSelectionWatch: (() => void) | undefined

onMounted(async () => {
  await nextTick()
  if (panelsStore.aiBrainstormPanel.suggestions.length === 0 && !isLoading.value) {
    await startSession()
  }
  skipSelectionWatch.value = false
  stopSelectionWatch = watch(
    () => [...diagramStore.selectedNodes],
    async (ids, prev) => {
      if (skipSelectionWatch.value || !prev) return
      if (ids.join(',') === prev.join(',')) return
      if (!panelsStore.aiBrainstormPanel.isOpen) return
      if (isLoading.value) return
      await startSession()
    }
  )
})

onUnmounted(() => {
  stopSelectionWatch?.()
})
</script>

<template>
  <aside
    class="ai-brainstorm-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-[26rem] max-w-[calc(100%-1.5rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.waterfall')"
  >
    <header class="flex shrink-0 flex-col gap-2 border-b border-slate-100 bg-gray-50/50 px-3 py-3">
      <div class="flex items-center justify-between gap-2">
        <h3 class="truncate text-sm font-semibold tracking-wide text-gray-800">
          {{ t('canvas.mindMapSideToolbar.waterfall') }}
        </h3>
        <div class="flex shrink-0 items-center gap-1">
          <span
            v-if="selectedIds.length > 0"
            class="mr-1 text-xs text-slate-500"
          >
            {{ selectedIds.length }} {{ t('nodePalette.selected') }}
          </span>
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
          <MindMapSidePanelCloseButton @close="handleClose" />
        </div>
      </div>

      <div
        v-if="showTabs"
        class="flex gap-1 overflow-x-auto rounded-lg bg-slate-100 p-0.5"
        :class="paletteTabStripGlowClass"
      >
        <template v-if="showStage2Tabs">
          <button
            v-for="parent in stage2Parents"
            :key="parent.id"
            type="button"
            class="shrink-0 rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
            :class="
              activeTabId === parent.name
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-slate-600 hover:text-gray-900'
            "
            :title="parent.name"
            @click="handleStageTab(parent.id, parent.name)"
          >
            {{ parent.name.length > 8 ? parent.name.slice(0, 7) + '…' : parent.name }}
          </button>
        </template>
        <template v-else>
          <button
            v-for="tab in sourceTabs"
            :key="tab.id"
            type="button"
            class="shrink-0 rounded-md px-2.5 py-1 text-xs font-medium transition-colors"
            :class="
              activeTabId === tab.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-slate-600 hover:text-gray-900'
            "
            @click="switchTab(tab.id)"
          >
            {{ tab.name }}
          </button>
        </template>
      </div>
    </header>

    <p class="ai-brainstorm-panel__hint shrink-0 border-b border-slate-100 px-3 py-2 text-[11px] leading-snug text-slate-500">
      {{ t('canvas.mindMapWaterfall.panelHint') }}
    </p>

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
        <p
          v-if="isLoading && suggestions.length > 0"
          class="flex items-center gap-1.5 text-xs text-slate-500"
        >
          <Loader2 class="h-3.5 w-3.5 shrink-0 animate-spin" />
          {{ t('nodePalette.generatingProgress', { count: suggestions.length }) }}
        </p>
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          draggable="true"
          class="brainstorm-suggestion-card cursor-grab rounded-xl border border-slate-200 px-3 py-2.5 transition-shadow active:cursor-grabbing hover:shadow-sm"
          :class="{ 'ring-2 ring-blue-400 ring-offset-1': selectedIds.includes(suggestion.id) }"
          :style="getNodeCardStyle(suggestion, selectedIds.includes(suggestion.id))"
          @click="toggleSelection(suggestion.id)"
          @dragstart="handleDragStart($event, suggestion)"
          @dragend="handleDragEnd"
        >
          <div class="flex items-start gap-2">
            <div
              v-if="selectedIds.includes(suggestion.id)"
              class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-500"
            >
              <Check class="h-3 w-3 text-white" />
            </div>
            <span
              dir="auto"
              class="block min-w-0 flex-1 text-sm leading-snug text-gray-800 line-clamp-3 break-words"
            >
              {{ suggestion.text }}
            </span>
          </div>
        </div>

        <div
          v-if="sessionId && !isLoading && suggestions.length > 0 && !isLoadingMore"
          class="mt-2 flex justify-center"
        >
          <button
            type="button"
            class="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
            @click="loadNextBatch"
          >
            {{ t('nodePalette.loadMore') }}
          </button>
        </div>
        <div
          v-if="isLoadingMore"
          class="mt-2 flex justify-center"
        >
          <Loader2 class="h-5 w-5 animate-spin text-blue-500" />
        </div>

        <p class="mt-2 rounded-lg bg-slate-50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-500">
          {{
            showNextButton
              ? t('nodePalette.helpNext')
              : t('nodePalette.helpFinish')
          }}
          <br />
          {{ t('canvas.mindMapWaterfall.dragHint') }}
        </p>
      </div>
    </div>

    <footer class="flex shrink-0 justify-center gap-2 border-t border-slate-100 px-3 py-3">
      <button
        type="button"
        class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="handleCancel"
      >
        {{ t('nodePalette.cancel') }}
      </button>
      <button
        type="button"
        class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
        :disabled="selectedIds.length === 0"
        @click="handleFinish"
      >
        {{ showNextButton ? t('nodePalette.next') : t('nodePalette.finish') }}
      </button>
    </footer>
  </aside>
</template>

<style scoped>
.ai-brainstorm-panel {
  max-height: calc(100% - 1.5rem);
}

.ai-brainstorm-panel__hint {
  white-space: pre-line;
}

.brainstorm-tab-strip--requesting {
  box-shadow: inset 0 -2px 0 rgb(59 130 246 / 0.45);
}

.brainstorm-tab-strip--streaming {
  box-shadow: inset 0 -2px 0 rgb(34 197 94 / 0.55);
}

.brainstorm-suggestion-card {
  user-select: none;
}
</style>
