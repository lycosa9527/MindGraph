<script setup lang="ts">
/**
 * Root concept modal (concept maps only): AI-suggested concepts to drag onto the canvas.
 * Uses the same node palette store/session as other diagrams but is separate from NodePalettePanel.
 *
 * Viewport: this component does not call fit/view events. Close paths use
 * `panelsStore.closeNodePalette()` (via dismiss / cancel / finishSelection in useNodePalette).
 * Desktop concept maps: no auto refit on palette close (`stores/panels.ts`) and no programmatic fit unless
 * the user uses zoom/fit controls (`userInitiated` on `view:fit_to_canvas_requested`).
 */
import { computed, nextTick, onMounted, watch } from 'vue'

import { ElButton, ElTooltip } from 'element-plus'

import { Check, Loader2, Plus, RefreshCw, X } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { PALETTE_CONCEPT_DRAG_MIME } from '@/composables/nodePalette/constants'
import { getNodePalette } from '@/composables/nodePalette/useNodePalette'
import { getLLMColor } from '@/config/llmModelColors'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

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
  sessionId,
  loadNextBatch,
  cancel,
  dismiss,
  selectedIds,
  toggleSelection,
  finishSelection,
  switchConceptMapTab,
  initializeConceptMapRootModal,
  refreshConceptMapRootModal,
  addConceptMapDomainTab,
} = getNodePalette({
  onError: (err) => notify.error(err),
})

const conceptMapTabs = computed(() => {
  const tabs = panelsStore.nodePalettePanel.conceptMapTabs ?? []
  const nodes = diagramStore.data?.nodes ?? []
  const nodeIds = new Set(nodes.map((n) => n.id))
  return tabs.filter((t) => t.id === 'topic' || t.id.startsWith('domain_') || nodeIds.has(t.id))
})

const conceptMapRootText = computed(() => {
  const id = getTopicRootConceptTargetId(diagramStore.data?.connections)
  if (!id) return ''
  const n = diagramStore.data?.nodes?.find((x) => x.id === id)
  return (n?.text ?? '').trim()
})

const paletteTabStripGlowClass = computed(() => {
  if (!isLoading.value && !isLoadingMore.value) return ''
  if (paletteStreamPhase.value === 'streaming') return 'palette-tab-strip-wrap--streaming'
  if (paletteStreamPhase.value === 'requesting') return 'palette-tab-strip-wrap--requesting'
  return 'palette-tab-strip-wrap--requesting'
})

watch(
  () => [conceptMapTabs.value, panelsStore.nodePalettePanel.mode] as const,
  ([tabs, mode]) => {
    if (!mode || !tabs.length) return
    const valid = tabs.some((t) => t.id === mode)
    if (!valid) switchConceptMapTab('topic')
  }
)

function tabButtonLabel(tab: { id: string; name: string }): string {
  if (tab.id === 'topic' && conceptMapRootText.value) {
    const t = conceptMapRootText.value
    return t.length > 10 ? `${t.slice(0, 9)}…` : t
  }
  const n = tab.name
  return n.length > 12 ? `${n.slice(0, 11)}…` : n
}

function tabTitleAttr(tab: { id: string; name: string }): string {
  if (tab.id === 'topic' && conceptMapRootText.value) {
    return t('rootConceptModal.tabTitleRoot', { text: conceptMapRootText.value })
  }
  return tab.name
}

function handleClose() {
  dismiss()
  emit('close')
}

async function handleFinish() {
  const closed = await finishSelection()
  if (closed) emit('close')
}

function handleCancel() {
  cancel()
  emit('close')
}

async function handleRefresh() {
  await refreshConceptMapRootModal()
}

async function handleAddDomain() {
  await addConceptMapDomainTab()
}

function handleDragStart(event: DragEvent, suggestion: NodeSuggestion) {
  if (!event.dataTransfer) return
  const payload: { text: string; relationship_label?: string } = { text: suggestion.text }
  const rel = (suggestion.relationship_label ?? '').trim()
  if (rel) payload.relationship_label = rel
  event.dataTransfer.setData(PALETTE_CONCEPT_DRAG_MIME, JSON.stringify(payload))
  event.dataTransfer.effectAllowed = 'copy'
}

function getNodeCardStyle(suggestion: { source_llm?: string }, isSelected: boolean) {
  const colors = suggestion.source_llm ? getLLMColor(suggestion.source_llm, uiStore.isDark) : null
  const selectedStyle = uiStore.isDark
    ? { borderColor: 'rgb(96, 165, 250)', backgroundColor: 'rgb(30, 58, 95)' }
    : { borderColor: 'rgb(59, 130, 246)', backgroundColor: 'rgb(239, 246, 255)' }
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

onMounted(async () => {
  await nextTick()
  await initializeConceptMapRootModal()
})
</script>

<template>
  <div class="root-concept-modal bg-white dark:bg-gray-800 flex flex-col h-full">
    <div
      class="panel-header px-4 flex justify-between border-b border-gray-200 dark:border-gray-700 shrink-0 h-14 items-center"
    >
      <div class="flex gap-3 min-w-0 flex-1 items-center">
        <h3 class="text-sm font-semibold text-gray-800 dark:text-white truncate shrink-0">
          {{ t('rootConceptModal.title') }}
        </h3>
        <div
          v-if="conceptMapTabs.length > 0"
          class="palette-tab-strip-wrap flex flex-1 min-w-0 items-center gap-1"
          :class="paletteTabStripGlowClass"
        >
          <div
            class="palette-tab-strip-inner flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
          >
            <button
              v-for="tab in conceptMapTabs"
              :key="tab.id"
              type="button"
              class="px-2 py-1 text-xs font-medium rounded-md transition-colors shrink-0"
              :class="
                panelsStore.nodePalettePanel.mode === tab.id
                  ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
              "
              :title="tabTitleAttr(tab)"
              @click="switchConceptMapTab(tab.id)"
            >
              {{ tabButtonLabel(tab) }}
            </button>
          </div>
          <ElTooltip
            :content="t('rootConceptModal.addBranchTooltip')"
            placement="bottom"
          >
            <button
              type="button"
              class="shrink-0 w-8 h-8 flex items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-500 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-40"
              :disabled="isLoading"
              :aria-label="t('rootConceptModal.addBranchAria')"
              @click="handleAddDomain"
            >
              <Plus class="w-4 h-4" />
            </button>
          </ElTooltip>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <div class="flex items-center gap-0">
          <ElTooltip
            :content="t('common.refresh')"
            placement="bottom"
          >
            <ElButton
              text
              circle
              size="small"
              class="shrink-0"
              :disabled="isLoading"
              @click="handleRefresh"
            >
              <RefreshCw :class="['w-4 h-4', isLoading ? 'animate-spin' : '']" />
            </ElButton>
          </ElTooltip>
          <ElButton
            text
            circle
            size="small"
            class="shrink-0"
            @click="handleClose"
          >
            <X class="w-4 h-4" />
          </ElButton>
        </div>
      </div>
    </div>

    <div class="panel-content flex-1 overflow-y-auto p-4 min-h-0">
      <div
        v-if="isLoading && suggestions.length === 0"
        class="flex flex-col items-center justify-center py-12 gap-4"
      >
        <Loader2 class="w-8 h-8 animate-spin text-blue-500" />
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ t('rootConceptModal.splittingLoading') }}
        </p>
      </div>

      <div
        v-else-if="errorMessage"
        class="py-4 text-sm text-red-600 dark:text-red-400"
      >
        {{ errorMessage }}
      </div>

      <div
        v-else
        class="flex flex-col gap-2"
      >
        <p
          v-if="isLoading && suggestions.length > 0"
          class="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5"
        >
          <Loader2 class="w-3.5 h-3.5 animate-spin shrink-0" />
          {{ t('nodePalette.generatingProgress', { count: suggestions.length }) }}
        </p>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="suggestion in suggestions"
            :key="suggestion.id"
            class="node-card p-3 rounded-lg border-2 transition-all border-gray-200 dark:border-gray-600"
            :class="[
              'cursor-pointer touch-manipulation',
              !suggestion.source_llm && !selectedIds.includes(suggestion.id)
                ? 'hover:border-blue-300 dark:hover:border-blue-700'
                : '',
            ]"
            :style="getNodeCardStyle(suggestion, selectedIds.includes(suggestion.id))"
            draggable="true"
            @click="toggleSelection(suggestion.id)"
            @dragstart="handleDragStart($event, suggestion)"
          >
            <div class="flex items-start gap-2">
              <div
                v-if="selectedIds.includes(suggestion.id)"
                class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center shrink-0 mt-0.5"
              >
                <Check class="w-3 h-3 text-white" />
              </div>
              <span
                dir="auto"
                class="text-sm text-gray-700 dark:text-gray-300 line-clamp-3 break-words min-w-0 flex-1"
                style="line-break: auto"
              >
                {{ suggestion.text }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="sessionId && !isLoading && suggestions.length > 0 && !isLoadingMore"
        class="mt-4 flex justify-center"
      >
        <el-button
          size="small"
          @click="loadNextBatch"
        >
          {{ t('nodePalette.loadMore') }}
        </el-button>
      </div>
      <div
        v-if="isLoadingMore"
        class="mt-4 flex justify-center"
      >
        <Loader2 class="w-5 h-5 animate-spin text-blue-500" />
      </div>

      <div
        v-if="!isLoading && suggestions.length > 0"
        class="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
      >
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{ t('rootConceptModal.helpFooter') }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {{ t('nodePalette.helpFinish') }}
        </p>
      </div>
    </div>

    <div
      class="panel-footer p-4 border-t border-gray-200 dark:border-gray-700 flex flex-wrap gap-2 justify-center shrink-0"
    >
      <ElButton
        size="default"
        @click="handleCancel"
      >
        {{ t('nodePalette.cancel') }}
      </ElButton>
      <ElButton
        type="primary"
        size="default"
        :disabled="selectedIds.length === 0"
        @click="handleFinish"
      >
        {{ t('nodePalette.finish') }}
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
@property --palette-border-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.root-concept-modal {
  display: flex;
  flex-direction: column;
}

.palette-tab-strip-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  border-radius: 0.5rem;
}

.palette-tab-strip-wrap--requesting,
.palette-tab-strip-wrap--streaming {
  padding: 2px;
}

.palette-tab-strip-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 2px;
  --palette-border-angle: 0deg;
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: palette-border-travel 2.5s linear infinite;
  transition: opacity 0.15s ease;
}

.palette-tab-strip-wrap--requesting::before {
  opacity: 1;
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 50deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 230deg,
    #d6d3d1 310deg,
    #e7e5e4 360deg
  );
}

.palette-tab-strip-wrap--streaming::before {
  opacity: 1;
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 50deg,
    #86efac 130deg,
    #22c55e 180deg,
    #4ade80 230deg,
    #d6d3d1 310deg,
    #e7e5e4 360deg
  );
}

:global(.dark) .palette-tab-strip-wrap--requesting::before {
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #1f2937 0deg,
    #374151 50deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 230deg,
    #374151 310deg,
    #1f2937 360deg
  );
}

:global(.dark) .palette-tab-strip-wrap--streaming::before {
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #1f2937 0deg,
    #374151 50deg,
    #4ade80 130deg,
    #16a34a 180deg,
    #86efac 230deg,
    #374151 310deg,
    #1f2937 360deg
  );
}

@keyframes palette-border-travel {
  to {
    --palette-border-angle: 360deg;
  }
}

.node-card {
  border-radius: 0.5rem;
}
</style>
