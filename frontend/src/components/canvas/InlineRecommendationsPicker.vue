<script setup lang="ts">
/**
 * InlineRecommendationsPicker - Bottom bar picker for diagram auto-completion
 *
 * Trigger: User fixes topic, double-clicks node to edit, then presses Tab.
 * AI streams recommendations. User presses 1-5 to select, - and = for prev/next page.
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useInlineRecommendations } from '@/composables/editor/useInlineRecommendations'
import { useDiagramStore, useInlineRecommendationsStore } from '@/stores'
import type { DiagramNode } from '@/types'
import {
  conceptMapUsesRelationshipInlineRec,
  getConceptMapPrimaryIncidentConnection,
} from '@/utils/conceptMapInlineRec'

const diagramStore = useDiagramStore()
const store = useInlineRecommendationsStore()
const { activeEntry, activePage, activeTotalPages, canPrevPage, canNextPage } = storeToRefs(store)
const { selectOption, prevPage, nextPage, isLoadingMoreFor } = useInlineRecommendations()

const activeNodeId = computed(() => activeEntry.value?.[0] ?? null)
const isLoadingMore = computed(() =>
  activeNodeId.value ? isLoadingMoreFor(activeNodeId.value) : false
)

/**
 * Double-bubble differences + bridge map pair cells: show Tab rec as A-over-B (fraction-style),
 * not "a | b".
 */
const isFractionPairTabRec = computed(() => {
  const id = activeNodeId.value ?? ''
  if (diagramStore.type === 'double_bubble_map') {
    return id.startsWith('left-diff-') || id.startsWith('right-diff-')
  }
  if (diagramStore.type === 'bridge_map') {
    return /^pair-\d+-left$/.test(id) || /^pair-\d+-right$/.test(id)
  }
  return false
})

function parsePairedOption(
  opt: string
): { top: string; bottom: string; dimension?: string } | null {
  if (!opt.includes('|')) return null
  const parts = opt.split('|').map((s) => s.trim())
  if (parts.length < 2) return null
  return {
    top: parts[0] ?? '',
    bottom: parts[1] ?? '',
    dimension: parts.length >= 3 ? parts.slice(2).join('|').trim() : undefined,
  }
}

const pickerRows = computed(() => {
  const entry = activeEntry.value
  if (!entry) return []
  return entry[1].map((opt, idx) => ({
    opt,
    idx,
    pair: isFractionPairTabRec.value ? parsePairedOption(opt) : null,
  }))
})

/**
 * Compared to option rows: concept map Tab can target relationship labels (linked node) or concept
 * text (isolated); relationship mode highlights against the deterministic primary incident edge label.
 */
const currentHighlightText = computed(() => {
  const entry = activeEntry.value
  if (!entry) return ''
  const nid = entry[0]
  if (
    diagramStore.type === 'concept_map' &&
    conceptMapUsesRelationshipInlineRec(nid, diagramStore.data?.connections)
  ) {
    const conn = getConceptMapPrimaryIncidentConnection(nid, diagramStore.data?.connections)
    return ((conn?.label ?? '') as string).trim()
  }
  const node = diagramStore.data?.nodes?.find((n) => n.id === nid) as DiagramNode | undefined
  return (node?.text ?? '').trim()
})

/** Top line of fraction = left-diff / pair-*-left; bottom = right-diff / pair-*-right */
function isLeftLineOfPair(nodeId: string): boolean {
  if (nodeId.startsWith('left-diff-')) return true
  if (nodeId.startsWith('right-diff-')) return false
  if (nodeId.endsWith('-left')) return true
  if (nodeId.endsWith('-right')) return false
  return true
}

/** For fraction rows, compare the line that matches this node (left vs right cell). */
function isRowHighlighted(
  row: { opt: string; pair: ReturnType<typeof parsePairedOption> },
  nodeId: string,
  nodeText: string
): boolean {
  if (!row.pair || !isFractionPairTabRec.value) {
    return nodeText === row.opt
  }
  const line = isLeftLineOfPair(nodeId) ? row.pair.top : row.pair.bottom
  return line.trim() === nodeText
}

/** Defense: clear stale options when node was deleted via another path */
watch(
  () => [activeEntry.value, diagramStore.data?.nodes] as const,
  ([entry]) => {
    if (!entry) return
    const nodeExists = diagramStore.data?.nodes?.some((n) => n.id === entry[0])
    if (!nodeExists) {
      store.invalidateForNode(entry[0])
    }
  },
  { immediate: true }
)

async function handleKeydown(event: KeyboardEvent) {
  const entry = activeEntry.value
  if (!entry) return
  if (event.key === '-') {
    event.preventDefault()
    event.stopPropagation()
    if (canPrevPage.value) prevPage(entry[0])
    return
  }
  if (event.key === '=') {
    event.preventDefault()
    event.stopPropagation()
    if (canNextPage.value || isLoadingMore.value) await nextPage(entry[0])
    return
  }

  const num =
    event.key === '1'
      ? 1
      : event.key === '2'
        ? 2
        : event.key === '3'
          ? 3
          : event.key === '4'
            ? 4
            : event.key === '5'
              ? 5
              : 0
  if (num > 0 && num <= entry[1].length) {
    event.preventDefault()
    event.stopPropagation()
    selectOption(entry[0], num - 1)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown, { capture: true })
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown, { capture: true })
})
</script>

<template>
  <div
    v-if="activeEntry"
    class="inline-recommendations-picker flex items-center gap-2 shrink-0"
    :class="isFractionPairTabRec ? 'min-h-[4.5rem] py-1' : ''"
  >
    <span
      class="picker-options flex flex-wrap gap-x-2 gap-y-1 text-xs"
      :class="
        isFractionPairTabRec
          ? 'items-stretch min-h-[3.5rem]'
          : 'items-center min-h-[1.5rem] gap-y-0.5'
      "
    >
      <span
        v-for="row in pickerRows"
        :key="row.idx"
        class="picker-option px-1.5 py-0.5 rounded cursor-pointer transition-colors flex gap-1.5 items-center"
        :class="[
          activeEntry && isRowHighlighted(row, activeEntry[0], currentHighlightText)
            ? 'bg-green-100 dark:bg-green-900/50 font-medium'
            : 'hover:bg-green-50 dark:hover:bg-green-900/30',
          isFractionPairTabRec && row.pair ? 'picker-option--fraction' : '',
        ]"
        @click="selectOption(activeEntry![0], row.idx)"
      >
        <span class="font-semibold text-green-600 dark:text-green-400 shrink-0">{{
          row.idx + 1
        }}</span>
        <div
          v-if="isFractionPairTabRec && row.pair"
          class="inline-rec-fraction inline-flex w-max min-w-0 max-w-[11rem] shrink-0 flex-col items-stretch gap-0.5"
        >
          <span
            dir="auto"
            class="text-center text-blue-600 dark:text-blue-400 leading-snug text-[11px] break-words"
            style="line-break: auto"
            >{{ row.pair.top }}</span
          >
          <div
            class="fraction-rule h-px w-full min-w-0 shrink-0 bg-gray-400/90 dark:bg-gray-500"
            aria-hidden="true"
          />
          <span
            dir="auto"
            class="text-center text-amber-600 dark:text-amber-400 leading-snug text-[11px] break-words"
            style="line-break: auto"
            >{{ row.pair.bottom }}</span
          >
          <span
            v-if="row.pair.dimension"
            class="text-center text-[9px] text-gray-500 dark:text-gray-400 leading-tight truncate max-w-full"
            :title="row.pair.dimension"
            >{{ row.pair.dimension }}</span
          >
        </div>
        <span
          v-else
          class="min-w-0 whitespace-nowrap"
          >{{ row.opt }}</span
        >
      </span>
    </span>
    <span
      v-if="canPrevPage || canNextPage || isLoadingMore"
      class="picker-nav flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
    >
      <button
        v-if="canPrevPage"
        type="button"
        class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
        aria-label="Previous page"
        @click="activeEntry && prevPage(activeEntry[0])"
      >
        -
      </button>
      <span
        v-if="activeTotalPages > 1"
        class="tabular-nums"
      >
        {{ activePage + 1 }}/{{ activeTotalPages }}
      </span>
      <button
        v-if="canNextPage || isLoadingMore"
        type="button"
        class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
        aria-label="Next page"
        :disabled="isLoadingMore"
        @click="activeEntry && nextPage(activeEntry[0])"
      >
        =
      </button>
    </span>
  </div>
</template>

<style scoped>
.picker-option {
  white-space: nowrap;
}
.picker-option--fraction {
  white-space: normal;
}
</style>
