/**
 * Concept map — linked concepts: Tab without opening inline edit mirrors “select → Tab”.
 * Isolated concepts still rely on edit → Tab (concept wording) from InlineEditableText.
 */
import { onMounted, onUnmounted } from 'vue'

import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  useAuthStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
} from '@/stores'
import { conceptMapUsesRelationshipInlineRec } from '@/utils/conceptMapInlineRec'

function isTypingUiTarget(el: EventTarget | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false
  if (el.isContentEditable) return true
  const tag = el.tagName?.toLowerCase?.() ?? ''
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
  return !!(el.closest?.('.inline-edit-input') || el.closest?.('.inline-edit-wrapper'))
}

function keyEventFromDiagramUi(e: KeyboardEvent): boolean {
  if (e.target instanceof HTMLElement && e.target.closest?.('.diagram-canvas')) {
    return true
  }
  const ae = document.activeElement
  return ae instanceof HTMLElement && !!ae.closest?.('.diagram-canvas')
}

export function useConceptMapRelationshipTabFromSelection(options: {
  startRecommendations: (nodeId: string) => void | Promise<unknown>
}): void {
  const diagramStore = useDiagramStore()
  const inlineRecStore = useInlineRecommendationsStore()
  const llmResultsStore = useLLMResultsStore()
  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  function onKeyDownCapture(e: KeyboardEvent): void {
    if (e.key !== 'Tab') return
    if (e.shiftKey) return
    if (!e.isTrusted) return
    if (diagramStore.type !== 'concept_map') return
    if (!keyEventFromDiagramUi(e)) return
    if (isTypingUiTarget(e.target)) return

    const selected = diagramStore.selectedNodes
    if (!selected?.length || selected.length !== 1) return

    const nodeId = selected[0]
    const connections = diagramStore.data?.connections ?? []
    if (!conceptMapUsesRelationshipInlineRec(nodeId, connections)) return

    const nodes = diagramStore.data?.nodes ?? []
    const node = nodes.find((n: { id?: string }) => n.id === nodeId)
    if (
      !node ||
      !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
    )
      return

    if (!inlineRecStore.isReady) return

    if (!llmResultsStore.selectedModel) {
      notify.warning(
        t(
          'notification.conceptMapTabNeedsAi',
          'Please enable 「启动 AI」 in the bar before Tab recommendations'
        )
      )
      e.preventDefault()
      e.stopPropagation()
      return
    }

    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      e.preventDefault()
      e.stopPropagation()
      return
    }

    e.preventDefault()
    e.stopPropagation()
    void options.startRecommendations(nodeId)
  }

  onMounted(() => window.addEventListener('keydown', onKeyDownCapture, true))

  onUnmounted(() => window.removeEventListener('keydown', onKeyDownCapture, true))
}
