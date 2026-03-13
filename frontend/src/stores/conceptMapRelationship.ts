/**
 * Concept Map Relationship Store - transient state for AI-generated label picker
 *
 * When user drags concepts to create a link, the API returns 3-5 relationship labels.
 * This store holds those options until the user selects one or clicks the canvas to clear.
 *
 * Kept separate from the diagram store because:
 * - Frequently updated (on each new link)
 * - Frequently cleared (pane click, select, edit, reset)
 * - Concept-map-specific UI state, not diagram data
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

export const useConceptMapRelationshipStore = defineStore(
  'conceptMapRelationship',
  () => {
    /** connectionId -> list of relationship label options (3–5) */
    const options = ref<Record<string, string[]>>({})

    /** First connection with options, for the bottom bar picker (we show one at a time) */
    const activeEntry = computed((): [string, string[]] | null => {
      const entries = Object.entries(options.value)
      return entries.length > 0 ? entries[0] : null
    })

    function setOptions(connectionId: string, labels: string[]): void {
      options.value = { [connectionId]: labels }
    }

    function clearConnection(connectionId: string): void {
      const next = { ...options.value }
      delete next[connectionId]
      options.value = next
    }

    function clearAll(): void {
      options.value = {}
    }

    return {
      options,
      activeEntry,
      setOptions,
      clearConnection,
      clearAll,
    }
  }
)
