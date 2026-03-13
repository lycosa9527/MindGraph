<script setup lang="ts">
/**
 * ConceptMapLabelPicker - Bottom bar label picker for concept map relationship options
 *
 * When user drags concepts to create a link, AI generates 3-5 labels.
 * This component shows them in the bottom bar with numbers; user presses 1-5 to select.
 * Clicking canvas clears the labels.
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useConceptMapRelationshipStore } from '@/stores/conceptMapRelationship'
import { useConceptMapRelationship } from '@/composables/useConceptMapRelationship'
import { useDiagramStore } from '@/stores'

const relationshipStore = useConceptMapRelationshipStore()
const diagramStore = useDiagramStore()
const { activeEntry } = storeToRefs(relationshipStore)
const { selectOption } = useConceptMapRelationship()

/** Current label for the active connection (to highlight selected option) */
const currentLabel = computed(() => {
  const entry = activeEntry.value
  if (!entry) return ''
  const conn = diagramStore.data?.connections?.find((c) => c.id === entry[0])
  return (conn?.label ?? '').trim()
})

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

function handleKeydown(event: KeyboardEvent) {
  const entry = activeEntry.value
  if (!entry) return
  const target = event.target as HTMLElement
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return
  const num = event.key === '1' ? 1 : event.key === '2' ? 2 : event.key === '3' ? 3 : event.key === '4' ? 4 : event.key === '5' ? 5 : 0
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
  </div>
</template>

<style scoped>
.label-picker-option {
  white-space: nowrap;
}
</style>
