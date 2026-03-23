<script setup lang="ts">
/**
 * Bottom bar: root concept alternatives (− / = / 0–5); 5 per page
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { Equal, Loader2, Minus } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useDiagramStore } from '@/stores/diagram'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

const store = useConceptMapRootConceptReviewStore()
const diagramStore = useDiagramStore()
const { t } = useLanguage()

const currentRootText = computed(() => {
  const id = getTopicRootConceptTargetId(diagramStore.data?.connections)
  if (!id) return ''
  const n = diagramStore.data?.nodes?.find((x) => x.id === id)
  return (n?.text ?? '').trim()
})

const selectedSlot = ref(0)

const visibleRows = computed(() => store.visibleSuggestionRows)

const labels = computed(() => ({
  suggestionsEmpty: t('conceptMapPicker.suggestionsEmpty'),
}))

function applySlot(idx: number): void {
  selectedSlot.value = idx
  if (idx === 0) return
  const row = visibleRows.value[idx - 1]
  if (row) store.applyRootConceptText(row.text)
}

function handleKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return
  if (target?.isContentEditable) return

  if (event.key === '-') {
    event.preventDefault()
    event.stopPropagation()
    if (store.canPrevSuggestionPage) store.prevSuggestionPage()
    return
  }
  if (event.key === '=') {
    event.preventDefault()
    event.stopPropagation()
    void store.nextSuggestionPageOrLoad()
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
              : event.key === '0'
                ? 0
                : -1
  if (num === 0) {
    event.preventDefault()
    event.stopPropagation()
    selectedSlot.value = 0
    return
  }
  if (num >= 1 && num <= 5 && num - 1 < visibleRows.value.length) {
    event.preventDefault()
    event.stopPropagation()
    applySlot(num)
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
  <div class="concept-root-concept-picker flex flex-col gap-2 min-w-0 w-fit max-w-full">
    <div class="flex flex-col gap-2 min-w-0 w-fit max-w-full">
      <div class="flex items-start justify-between gap-2 min-w-0">
        <p class="text-[10px] text-gray-500 dark:text-gray-400 leading-snug flex-1 min-w-0">
          {{ t('conceptMapPicker.rootAlternativesHint', { pageSize: store.PAGE_SIZE }) }}
        </p>
        <div class="flex items-center gap-0.5 shrink-0 text-gray-500 dark:text-gray-400">
          <button
            v-if="store.canPrevSuggestionPage"
            type="button"
            class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
            aria-label="Previous"
            @click="store.prevSuggestionPage()"
          >
            <Minus class="w-3.5 h-3.5" />
          </button>
          <span
            v-if="store.totalSuggestionPages > 1 || store.suggestionRows.length > 0"
            class="tabular-nums text-[10px]"
          >
            {{ store.suggestionPage + 1 }}/{{ store.totalSuggestionPages }}
          </span>
          <button
            type="button"
            class="px-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-40"
            :disabled="store.loadingMoreSuggestions"
            aria-label="Next"
            @click="store.nextSuggestionPageOrLoad()"
          >
            <Equal class="w-3.5 h-3.5" />
          </button>
          <Loader2
            v-if="store.loadingMoreSuggestions"
            class="w-3.5 h-3.5 animate-spin shrink-0"
          />
        </div>
      </div>

      <p
        v-if="!store.loadingMoreSuggestions && store.suggestionRows.length === 0"
        class="text-[10px] text-amber-700 dark:text-amber-300"
      >
        {{ labels.suggestionsEmpty }}
      </p>

      <div class="flex flex-col gap-1.5 w-full min-w-0">
        <button
          type="button"
          class="suggestion-row flex gap-2 w-full min-w-0 rounded-lg border px-2.5 py-2 text-left text-[11px] leading-snug transition-colors"
          :class="
            selectedSlot === 0
              ? 'border-blue-500 bg-blue-50/90 dark:bg-blue-950/40 ring-1 ring-blue-400/50'
              : 'border-gray-200 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/50 hover:border-blue-300 dark:hover:border-blue-600'
          "
          @click="selectedSlot = 0"
        >
          <span
            class="font-mono text-xs font-semibold tabular-nums text-blue-600 dark:text-blue-400 shrink-0 pt-0.5"
            >0</span
          >
          <span class="min-w-0 flex-1 text-gray-800 dark:text-gray-100 break-words">
            {{ t('conceptMapPicker.currentRootConcept') }}
            <span v-if="currentRootText" class="block mt-0.5 text-gray-600 dark:text-gray-300">{{
              currentRootText
            }}</span>
          </span>
        </button>
        <button
          v-for="(row, idx) in visibleRows"
          :key="`${store.suggestionPage}-${idx}-${row.text.slice(0, 24)}`"
          type="button"
          class="suggestion-row flex gap-2 w-full min-w-0 rounded-lg border px-2.5 py-2 text-left text-[11px] leading-snug transition-colors"
          :class="
            selectedSlot === idx + 1
              ? 'border-blue-500 bg-blue-50/90 dark:bg-blue-950/40 ring-1 ring-blue-400/50'
              : 'border-gray-200 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/50 hover:border-blue-300 dark:hover:border-blue-600'
          "
          :title="row.text"
          @click="applySlot(idx + 1)"
        >
          <span
            class="font-mono text-xs font-semibold tabular-nums text-blue-600 dark:text-blue-400 shrink-0 pt-0.5"
            >{{ idx + 1 }}</span
          >
          <span
            class="min-w-0 flex-1 text-gray-800 dark:text-gray-100 break-words whitespace-normal"
            >{{ row.text }}</span
          >
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.suggestion-row {
  align-items: flex-start;
}
</style>
