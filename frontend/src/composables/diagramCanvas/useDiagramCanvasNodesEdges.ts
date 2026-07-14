import { type MaybeRefOrGetter, computed, toValue } from 'vue'

import { storeToRefs } from 'pinia'

import { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { useDiagramStore } from '@/stores'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import {
  getMindMapCollapseHiddenIds,
  getMindMapCollapsedPaths,
} from '@/stores/diagram/mindMapCollapse'
import { useUIStore } from '@/stores/ui'
import { effectiveMindMapCanvasMode } from '@/utils/mindMapCanvasMode'

export interface UseDiagramCanvasNodesEdgesOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  branchMove: ReturnType<typeof useBranchMoveDrag>
  collabLockedNodeIds: MaybeRefOrGetter<string[]>
  mindMapSlideFocusNodeId?: MaybeRefOrGetter<string | null | undefined>
  mindMapSlideDimFocusNodeIds?: MaybeRefOrGetter<Set<string> | null | undefined>
}

export function useDiagramCanvasNodesEdges(options: UseDiagramCanvasNodesEdgesOptions) {
  const { diagramStore, branchMove, collabLockedNodeIds, mindMapSlideFocusNodeId, mindMapSlideDimFocusNodeIds } = options
  const indicatorStore = useCanvasNodeIndicatorsStore()
  const { mindMapCanvasMode } = storeToRefs(useUIStore())
  const featureFlagsStore = useFeatureFlagsStore()
  const effectiveMindMapMode = computed(() =>
    effectiveMindMapCanvasMode(
      mindMapCanvasMode.value,
      featureFlagsStore.getFeatureMindmapV2Canvas()
    )
  )

  const storeNodes = computed(() => diagramStore.vueFlowNodes)
  const storeEdges = computed(() => diagramStore.vueFlowEdges)

  const mindMapCollapseHiddenIds = computed(() => {
    if (effectiveMindMapMode.value !== 'v2') return new Set<string>()
    const dtype = diagramStore.type
    if (dtype !== 'mindmap' && dtype !== 'mind_map') return new Set<string>()
    const data = diagramStore.data
    if (!data?.nodes || !data.connections) return new Set<string>()
    const paths = getMindMapCollapsedPaths(data)
    if (paths.length === 0) return new Set<string>()
    return getMindMapCollapseHiddenIds(
      data.nodes,
      data.connections,
      paths,
      diagramStore.getMindMapDescendantIds
    )
  })

  const nodes = computed(() => {
    const hidden = branchMove.state.value.hiddenIds
    const collapseHidden = mindMapCollapseHiddenIds.value
    let list = storeNodes.value
    if (hidden.size > 0 || collapseHidden.size > 0) {
      list = list.filter((n) => !hidden.has(n.id) && !collapseHidden.has(n.id))
    }
    const locked = toValue(collabLockedNodeIds)
    if (locked.length > 0) {
      const lockedSet = new Set(locked)
      list = list.map((n) => (lockedSet.has(n.id) ? { ...n, draggable: false } : n))
    }

    const workshopEditing = indicatorStore.workshopEditing
    const collabSelected = indicatorStore.collabSelected
    const tabRecActive = indicatorStore.tabRecActive
    const slideFocusNodeId = toValue(mindMapSlideFocusNodeId) ?? null
    const slideDimFocusNodeIds = toValue(mindMapSlideDimFocusNodeIds) ?? null

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
      if (slideFocusNodeId === n.id) {
        classes.push('mind-map-slide-focus')
      }
      if (slideDimFocusNodeIds && !slideDimFocusNodeIds.has(n.id)) {
        classes.push('mind-map-slide-dimmed')
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
    const collapseHidden = mindMapCollapseHiddenIds.value
    const baseList =
      hidden.size > 0 || collapseHidden.size > 0
        ? storeEdges.value.filter(
            (e) =>
              !hidden.has(e.source) &&
              !hidden.has(e.target) &&
              !collapseHidden.has(e.source) &&
              !collapseHidden.has(e.target)
          )
        : storeEdges.value

    const slideDimFocusNodeIds = toValue(mindMapSlideDimFocusNodeIds) ?? null
    const withSlideEdgeDim = baseList.map((e) => {
      const existingClass = typeof e.class === 'string' ? e.class : ''
      if (slideDimFocusNodeIds && slideDimFocusNodeIds.size > 0) {
        const inFocus =
          slideDimFocusNodeIds.has(e.source) && slideDimFocusNodeIds.has(e.target)
        if (inFocus) return { ...e, class: existingClass }
        const merged = existingClass
          ? `${existingClass} mind-map-slide-edge-dimmed`
          : 'mind-map-slide-edge-dimmed'
        return { ...e, class: merged }
      }
      const clearedClass = existingClass
        .split(/\s+/)
        .filter((token) => token && token !== 'mind-map-slide-edge-dimmed')
        .join(' ')
      return { ...e, class: clearedClass }
    })

    // Concept maps use edge-level tab-rec ant lines; always map them so that the
    // tab-rec-active class is explicitly cleared when the indicator is removed
    // (Vue Flow only updates a class attribute when the property is explicitly present).
    if (diagramStore.type !== 'concept_map') return withSlideEdgeDim

    const recEdgeIds = indicatorStore.tabRecEdgeIds
    const recSet = new Set(recEdgeIds)
    return withSlideEdgeDim.map((e) => {
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
