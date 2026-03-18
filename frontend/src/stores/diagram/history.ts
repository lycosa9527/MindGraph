import { computed } from 'vue'

import type { HistoryEntry } from '@/types'

import { MAX_HISTORY_SIZE } from './constants'
import type { DiagramContext } from './types'

export function useHistorySlice(ctx: DiagramContext) {
  const { data, history, historyIndex } = ctx

  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)

  function pushHistory(action: string): void {
    if (!data.value) return

    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    const entry: HistoryEntry = {
      data: JSON.parse(JSON.stringify(data.value)),
      timestamp: Date.now(),
      action,
    }

    history.value.push(entry)

    if (history.value.length > MAX_HISTORY_SIZE) {
      history.value.shift()
    } else {
      historyIndex.value++
    }
  }

  function undo(): boolean {
    if (!canUndo.value) return false

    historyIndex.value--
    const entry = history.value[historyIndex.value]
    if (entry) {
      data.value = JSON.parse(JSON.stringify(entry.data))
      return true
    }
    return false
  }

  function redo(): boolean {
    if (!canRedo.value) return false

    historyIndex.value++
    const entry = history.value[historyIndex.value]
    if (entry) {
      data.value = JSON.parse(JSON.stringify(entry.data))
      return true
    }
    return false
  }

  function clearHistory(): void {
    history.value = []
    historyIndex.value = -1
  }

  return { canUndo, canRedo, pushHistory, undo, redo, clearHistory }
}
