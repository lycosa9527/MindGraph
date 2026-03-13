<script setup lang="ts">
/**
 * ConceptMapLabelPicker - Bottom bar label picker for concept map relationship options
 *
 * Catapult-style: AI streams ~10 labels, we show first 5. User presses:
 * - 1-5: select option
 * - - : previous page
 * - = : next page (fetches more via next_batch when at end)
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useConceptMapRelationship } from '@/composables/useConceptMapRelationship'
import { useDiagramStore } from '@/stores'

const relationshipStore = useConceptMapRelationshipStore()
const diagramStore = useDiagramStore()
const {
  activeEntry,
  activePage,
  activeTotalPages,
  canPrevPage,
  canNextPage,
} = storeToRefs(relationshipStore)
const {
  selectOption,
  prevPage,
  nextPage,
  isLoadingMoreFor,
} = useConceptMapRelationship()

/** Current label for the active connection (to highlight selected option) */
const currentLabel = computed(() => {
  const entry = activeEntry.value
  if (!entry) return ''
  const conn = diagramStore.data?.connections?.find((c) => c.id === entry[0])
  return (conn?.label ?? '').trim()
})

const activeConnectionId = computed(() => activeEntry.value?.[0] ?? null)
const isLoadingMore = computed(() =>
  activeConnectionId.value
    ? isLoadingMoreFor(activeConnectionId.value)
    : false
)

/** Defense: clear stale options when connection was deleted via another path */
watch(
  () => [activeEntry.value, diagramStore.data?.connections] as const,
  ([entry]) => {
    if (!entry) return
    const connExists = diagramStore.data?.connections?.some((c) => c.id === entry[0])
    if (!connExists) {
      relationshipStore.clearConnection(entry[0])
    }
  },
  { immediate: true }
)

async function handleKeydown(event: KeyboardEvent) {
  const entry = activeEntry.value
  if (!entry) return
  const target = event.target as HTMLElement
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return

  if (event.key === '-') {
    event.preventDefault()
    if (canPrevPage.value) prevPage(entry[0])
    return
  }
  if (event.key === '=') {
    event.preventDefault()
    if (canNextPage.value || isLoadingMore.value) await nextPage(entry[0])
    return
  }

  const num =
    event.key === '1' ? 1
    : event.key === '2' ? 2
    : event.key === '3' ? 3
    : event.key === '4' ? 4
    : event.key === '5' ? 5
    : 0
  if (num > 0 && num <= entry[1].length) {
    event.preventDefault()
    selectOption(entry[0], num - 1)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div
    v-if="activeEntry"
    class="concept-map-label-picker flex items-center gap-2 shrink-0"
  >
    <span class="label-picker-options flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
      <span
        v-for="(opt, idx) in activeEntry[1]"
        :key="idx"
        class="label-picker-option px-1.5 py-0.5 rounded cursor-pointer transition-colors"
        :class="{
          'bg-blue-100 dark:bg-blue-900/50 font-medium': currentLabel === opt,
          'hover:bg-blue-50 dark:hover:bg-blue-900/30': currentLabel !== opt,
        }"
        @click="selectOption(activeEntry[0], idx)"
      >
        <span class="font-semibold text-blue-600 dark:text-blue-400">{{ idx + 1 }}</span>
        {{ opt }}
      </span>
    </span>
    <span
      v-if="canPrevPage || canNextPage || isLoadingMore"
      class="label-picker-nav flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
    >
      <button
        v-if="canPrevPage"
        type="button"
        class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
        :aria-label="'Previous page'"
        @click="activeEntry && prevPage(activeEntry[0])"
      >
        -
      </button>
      <span v-if="activeTotalPages > 1" class="tabular-nums">
        {{ activePage + 1 }}/{{ activeTotalPages }}
      </span>
      <button
        v-if="canNextPage || isLoadingMore"
        type="button"
        class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
        :aria-label="'Next page'"
        :disabled="isLoadingMore"
        @click="activeEntry && nextPage(activeEntry[0])"
      >
        =
      </button>
    </span>
  </div>
</template>

<style scoped>
.label-picker-option {
  white-space: nowrap;
}
</style>
