import { computed, onMounted, onUnmounted, ref } from 'vue'

import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores'
import { claimThinkingCoinEvent } from '@/utils/claimThinkingCoinEvent'

/** Hammer pick mode — survives panel close so user can focus on canvas. */
export const learningSheetPickActive = ref(false)

/** Top float bar (custom pick or random blank session). */
export const learningSheetFloatBarOpen = ref(false)

/** Float bar visibility before presentation; restored when leaving presentation. */
const learningSheetFloatBarBeforePresentation = ref(false)

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

export function learningSheetNeedsPresentationConfirm(): boolean {
  return learningSheetPickActive.value || learningSheetFloatBarOpen.value
}

function dismissLearningSheetFloatBar(): void {
  learningSheetPickActive.value = false
  learningSheetFloatBarOpen.value = false
}

/** Clear module-level learning-sheet UI when leaving canvas or resetting session. */
export function resetLearningSheetCustomModeUi(): void {
  learningSheetPickActive.value = false
  learningSheetFloatBarOpen.value = false
  learningSheetFloatBarBeforePresentation.value = false
}

export function toggleLearningSheetAnswersVisibility(): boolean {
  const diagramStore = useDiagramStore()
  if (!diagramStore.isLearningSheet) {
    return false
  }
  diagramStore.setLearningSheetShowAnswers(!diagramStore.learningSheetShowAnswers)
  return true
}

/** Re-open float bar after reload when diagram spec still has learning-sheet mode. */
export function restoreLearningSheetUiFromDiagram(): void {
  const diagramStore = useDiagramStore()
  if (!diagramStore.isLearningSheet) {
    resetLearningSheetCustomModeUi()
    return
  }
  learningSheetFloatBarOpen.value = true
  learningSheetPickActive.value = false
}

/**
 * Entering presentation: end hammer pick / hide float bar but keep blanked nodes
 * (teacher presents the worksheet as-is).
 */
export function suspendLearningSheetForPresentation(): void {
  const diagramStore = useDiagramStore()
  if (!diagramStore.isLearningSheet && !learningSheetFloatBarOpen.value) {
    learningSheetFloatBarBeforePresentation.value = false
    return
  }
  learningSheetFloatBarBeforePresentation.value = learningSheetFloatBarOpen.value
  dismissLearningSheetFloatBar()
}

/** Leaving presentation: restore float bar if still in learning-sheet mode. */
export function resumeLearningSheetAfterPresentation(): void {
  const diagramStore = useDiagramStore()
  if (
    learningSheetFloatBarBeforePresentation.value &&
    diagramStore.isLearningSheet &&
    !learningSheetFloatBarOpen.value
  ) {
    learningSheetFloatBarOpen.value = true
  }
  learningSheetFloatBarBeforePresentation.value = false
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

  function dismissFloatBar(): void {
    dismissLearningSheetFloatBar()
  }

  function activatePick(): void {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    diagramStore.setLearningSheetMode(true)
    customPickActive.value = true
    learningSheetFloatBarOpen.value = true
    void claimThinkingCoinEvent('learning_sheet_enable')
  }

  function startRandomLearningSheet(): void {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    customPickActive.value = false
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
      diagramStore.pushHistory(t('canvas.mindMapSideToolbar.learningSheetRandomBlankHistory'))
      learningSheetFloatBarOpen.value = true
      notify.success(t('canvas.toolbar.switchedLearningSheetMode'))
      void claimThinkingCoinEvent('learning_sheet_enable')
    }
  }

  function exitLearningSheet(): void {
    dismissFloatBar()
    learningSheetFloatBarBeforePresentation.value = false
    if (diagramStore.isLearningSheet) {
      diagramStore.restoreFromLearningSheetMode()
      diagramStore.pushHistory(t('canvas.toolbar.learningSheetRestored'))
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
    isFloatBarOpen: computed(() => learningSheetFloatBarOpen.value),
    activatePick,
    dismissFloatBar,
    deactivatePick: dismissFloatBar,
    startRandomLearningSheet,
    exitLearningSheet,
  }
}

export function useLearningSheetPickKeyboard(): void {
  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !learningSheetFloatBarOpen.value) return
    const target = event.target as HTMLElement | null
    if (
      target?.tagName === 'INPUT' ||
      target?.tagName === 'TEXTAREA' ||
      target?.isContentEditable
    ) {
      return
    }
    event.preventDefault()
    customPickActive.value = false
    learningSheetFloatBarOpen.value = false
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
  })
}
