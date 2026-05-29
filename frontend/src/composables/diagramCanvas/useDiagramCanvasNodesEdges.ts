import { type MaybeRefOrGetter, computed, toValue } from 'vue'

import { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { useDiagramStore } from '@/stores'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'

export interface UseDiagramCanvasNodesEdgesOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  branchMove: ReturnType<typeof useBranchMoveDrag>
  collabLockedNodeIds: MaybeRefOrGetter<string[]>
}

export function useDiagramCanvasNodesEdges(options: UseDiagramCanvasNodesEdgesOptions) {
  const { diagramStore, branchMove, collabLockedNodeIds } = options
  const indicatorStore = useCanvasNodeIndicatorsStore()

  const storeNodes = computed(() => diagramStore.vueFlowNodes)
  const storeEdges = computed(() => diagramStore.vueFlowEdges)

  const nodes = computed(() => {
    const hidden = branchMove.state.value.hiddenIds
    let list = storeNodes.value
    if (hidden.size > 0) {
      list = list.filter((n) => !hidden.has(n.id))
    }
    const locked = toValue(collabLockedNodeIds)
    if (locked.length > 0) {
      const lockedSet = new Set(locked)
      list = list.map((n) => (lockedSet.has(n.id) ? { ...n, draggable: false } : n))
    }

    const workshopEditing = indicatorStore.workshopEditing
    const collabSelected = indicatorStore.collabSelected
    const tabRecActive = indicatorStore.tabRecActive

    // Always map so every returned node has an explicit `class` property.
    // If we returned the original node objects (which have no `class` key) when
    // transitioning from "has indicator" → "no indicator", Vue Flow would skip
    // updating the class attribute entirely, leaving the previous indicator class
    // stuck on the DOM element.
    return list.map((n) => {
      const classes: string[] = []
      const extraStyle: Record<string, string> = {}

      const edit = workshopEditing.get(n.id)
      if (edit) {
        classes.push('workshop-editing')
        extraStyle['--workshop-ant-color'] = edit.antColor
        extraStyle['--editor-color'] = edit.editorColor
        // CSS var() values for the sticker ::after — content: var(--editor-emoji) ... var(--editor-label)
        extraStyle['--editor-emoji'] = `"${edit.emoji}"`
        extraStyle['--editor-label'] = `"${edit.label}"`
      }
      // collab-remote-selected is suppressed when workshop-editing is also active
      if (collabSelected.has(n.id) && !edit) {
        classes.push('collab-remote-selected')
      }
      if (tabRecActive === n.id) {
        classes.push('tab-rec-active')
      }

      // Always return a new object with an explicit `class` value (even '').
      // This guarantees Vue Flow sees the class key and clears any previously
      // applied indicator class when the indicator is removed.
      const existingClass = typeof n.class === 'string' ? n.class : ''
      const mergedClass = [existingClass, ...classes].filter(Boolean).join(' ')

      if (Object.keys(extraStyle).length === 0) {
        return { ...n, class: mergedClass }
      }

      const mergedStyle =
        typeof n.style === 'object' && n.style !== null
          ? { ...n.style, ...extraStyle }
          : { ...extraStyle }

      return { ...n, class: mergedClass, style: mergedStyle }
    })
  })

  const nodesLength = computed(() => nodes.value.length)

  const edges = computed(() => {
    if (diagramStore.type === 'brace_map') {
      return []
    }
    const hidden = branchMove.state.value.hiddenIds
    const baseList =
      hidden.size > 0
        ? storeEdges.value.filter((e) => !hidden.has(e.source) && !hidden.has(e.target))
        : storeEdges.value

    // Concept maps use edge-level tab-rec ant lines; always map them so that the
    // tab-rec-active class is explicitly cleared when the indicator is removed
    // (Vue Flow only updates a class attribute when the property is explicitly present).
    if (diagramStore.type !== 'concept_map') return baseList

    const recEdgeIds = indicatorStore.tabRecEdgeIds
    const recSet = new Set(recEdgeIds)
    return baseList.map((e) => {
      const existingClass = typeof e.class === 'string' ? e.class : ''
      if (recSet.has(e.id)) {
        const merged = existingClass ? `${existingClass} tab-rec-active` : 'tab-rec-active'
        return { ...e, class: merged }
      }
      return { ...e, class: existingClass }
    })
  })

  return { nodes, edges, nodesLength }
}
