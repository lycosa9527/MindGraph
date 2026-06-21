import { computed, onMounted, onUnmounted, ref } from 'vue'

import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores'
import { claimThinkingCoinEvent } from '@/utils/claimThinkingCoinEvent'

/** Hammer pick mode — survives panel close so user can focus on canvas. */
export const learningSheetPickActive = ref(false)

const customPickActive = learningSheetPickActive

const PROTECTED_NODE_IDS = new Set([
  'topic',
  'event',
  'flow-topic',
  'left-topic',
  'right-topic',
  'dimension-label',
  'outer-boundary',
])

function isProtectedNodeId(
  nodeId: string,
  diagramStore: ReturnType<typeof useDiagramStore>
): boolean {
  if (PROTECTED_NODE_IDS.has(nodeId)) return true
  const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
  if (!node) return true
  return node.type === 'topic' || node.type === 'center' || node.type === 'boundary'
}

function t(key: string): string {
  return String(i18n.global.t(key))
}

export function isLearningSheetCustomPickActive(): boolean {
  return customPickActive.value
}

/** Safe to call from node click handlers (outside component setup). */
export function handleLearningSheetPickNodeClick(nodeId: string): boolean {
  if (!customPickActive.value) return false

  const diagramStore = useDiagramStore()

  if (!diagramStore.isLearningSheet) {
    diagramStore.setLearningSheetMode(true)
  }

  if (isProtectedNodeId(nodeId, diagramStore)) {
    notify.warning(t('canvas.mindMapSideToolbar.learningSheetProtectedNode'))
    return true
  }

  const result = diagramStore.toggleLearningSheetNodeBlank(nodeId)
  if (result === 'blanked') {
    diagramStore.pushHistory(t('canvas.mindMapSideToolbar.learningSheetBlankHistory'))
  } else if (result === 'restored') {
    diagramStore.pushHistory(t('canvas.mindMapSideToolbar.learningSheetRestoreHistory'))
  }
  return true
}

export function useLearningSheetCustomMode() {
  const diagramStore = useDiagramStore()

  const isPickActive = computed(() => customPickActive.value)
  const blankCount = computed(() => {
    const nodes = diagramStore.data?.nodes
    if (!nodes?.length) return 0
    return nodes.filter((n) => diagramStore.isNodeBlankedForLearningSheet(n.id)).length
  })
  const isLearningSheetActive = computed(() => diagramStore.isLearningSheet)

  function deactivatePick(): void {
    customPickActive.value = false
  }

  function activatePick(): void {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    // Always sync flags + rebuild answers from actually blanked nodes (clears stale metadata).
    diagramStore.setLearningSheetMode(true)
    customPickActive.value = true
    void claimThinkingCoinEvent('learning_sheet_enable')
  }

  function startRandomLearningSheet(): void {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    deactivatePick()
    const spec = diagramStore.getSpecForSave()
    if (spec && diagramStore.type) {
      diagramStore.loadFromSpec(
        {
          ...spec,
          is_learning_sheet: true,
          hidden_node_percentage: 0.2,
        },
        diagramStore.type
      )
      notify.success(t('canvas.toolbar.switchedLearningSheetMode'))
      void claimThinkingCoinEvent('learning_sheet_enable')
    }
  }

  function exitLearningSheet(): void {
    deactivatePick()
    if (diagramStore.isLearningSheet) {
      diagramStore.restoreFromLearningSheetMode()
      notify.success(t('canvas.toolbar.switchedToRegular'))
    } else if (diagramStore.hasPreservedLearningSheet()) {
      diagramStore.clearLearningSheetPreservation()
      notify.success(t('canvas.toolbar.switchedToRegular'))
    }
  }

  return {
    isPickActive,
    blankCount,
    isLearningSheetActive,
    activatePick,
    deactivatePick,
    startRandomLearningSheet,
    exitLearningSheet,
  }
}

export function useLearningSheetPickKeyboard(): void {
  const { deactivatePick, isPickActive } = useLearningSheetCustomMode()

  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !isPickActive.value) return
    const target = event.target as HTMLElement | null
    if (
      target?.tagName === 'INPUT' ||
      target?.tagName === 'TEXTAREA' ||
      target?.isContentEditable
    ) {
      return
    }
    event.preventDefault()
    deactivatePick()
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
  })
}
