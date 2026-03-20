<script setup lang="ts">
/**
 * InlineRecommendationsPicker - Bottom bar picker for diagram auto-completion
 *
 * Trigger: User fixes topic, double-clicks node to edit, then presses Tab.
 * AI streams recommendations. User presses 1-5 to select, - and = for prev/next page.
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useInlineRecommendations } from '@/composables/useInlineRecommendations'
import { useDiagramStore, useInlineRecommendationsStore } from '@/stores'

const diagramStore = useDiagramStore()
const store = useInlineRecommendationsStore()
const { activeEntry, activePage, activeTotalPages, canPrevPage, canNextPage } = storeToRefs(store)
const { selectOption, prevPage, nextPage, isLoadingMoreFor } = useInlineRecommendations()

const activeNodeId = computed(() => activeEntry.value?.[0] ?? null)
const isLoadingMore = computed(() =>
  activeNodeId.value ? isLoadingMoreFor(activeNodeId.value) : false
)

/** Current text for the active node (to highlight selected option) */
const currentNodeText = computed(() => {
  const entry = activeEntry.value
  if (!entry) return ''
  const node = diagramStore.data?.nodes?.find((n) => n.id === entry[0])
  return (node?.text ?? '').trim()
})

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
  >
    <span
      class="picker-options flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs min-h-[1.5rem]"
    >
      <span
        v-for="(opt, idx) in activeEntry[1]"
        :key="idx"
        class="picker-option px-1.5 py-0.5 rounded cursor-pointer transition-colors"
        :class="{
          'bg-green-100 dark:bg-green-900/50 font-medium': currentNodeText === opt,
          'hover:bg-green-50 dark:hover:bg-green-900/30': currentNodeText !== opt,
        }"
        @click="selectOption(activeEntry![0], idx)"
      >
        <span class="font-semibold text-green-600 dark:text-green-400">{{ idx + 1 }}</span>
        {{ opt }}
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
</style>
