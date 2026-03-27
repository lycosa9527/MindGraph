import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { Position, getBezierPath } from '@vue-flow/core'

import { PALETTE_CONCEPT_DRAG_MIME } from '@/composables/nodePalette/constants'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore, useLLMResultsStore } from '@/stores'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

import {
  PILL_HALF_HEIGHT,
  PILL_HALF_WIDTH,
  getConceptNodeCenter,
  getConceptNodeEdgePoint,
  getEdgePoint,
  getPositionsFromAngle,
} from './conceptMapLinkPreviewGeometry'

type DiagramStore = ReturnType<typeof useDiagramStore>

const CONCEPT_LINK_DATA_TYPE = 'application/mindgraph-concept-link'

export function useDiagramCanvasConceptMapLink(options: {
  diagramStore: DiagramStore
  screenToFlowCoordinate: (pos: { x: number; y: number }) => { x: number; y: number }
  t: (key: string) => string
  generateRelationship: (
    connectionId: string,
    sourceId: string,
    targetId: string
  ) => void | Promise<unknown>
}): {
  linkDragSourceId: Ref<string | null>
  linkDragCursor: Ref<{ x: number; y: number } | null>
  linkDragTargetNodeId: Ref<string | null>
  linkPreviewPath: ComputedRef<string | null>
  linkPreviewShowArrow: ComputedRef<boolean>
  handleConceptMapDragOver: (event: DragEvent) => void
  handleConceptMapDrop: (event: DragEvent) => void
} {
  const { diagramStore, screenToFlowCoordinate, t, generateRelationship } = options
  const llmResultsStore = useLLMResultsStore()

  const linkDragSourceId = ref<string | null>(null)
  const linkDragCursor = ref<{ x: number; y: number } | null>(null)
  const linkDragTargetNodeId = ref<string | null>(null)

  function findConnectionBetween(
    sourceId: string,
    targetId: string
  ): { id: string; source: string; target: string } | null {
    const connections = diagramStore.data?.connections ?? []
    const conn = connections.find(
      (c) =>
        (c.source === sourceId && c.target === targetId) ||
        (c.source === targetId && c.target === sourceId)
    )
    return conn?.id ? { id: conn.id, source: conn.source, target: conn.target } : null
  }

  function handleConceptMapLinkDrop(payload: { sourceId: string; targetId: string }) {
    if (diagramStore.type !== 'concept_map') return
    const connId = diagramStore.addConnection(payload.sourceId, payload.targetId, '')
    if (connId) {
      diagramStore.pushHistory('Add link')
    }
    if (llmResultsStore.selectedModel) {
      const idToUse = connId ?? findConnectionBetween(payload.sourceId, payload.targetId)?.id
      if (idToUse) {
        generateRelationship(idToUse, payload.sourceId, payload.targetId)
      }
    }
  }

  function handleConceptMapLabelCleared(payload: {
    connectionId: string
    sourceId: string
    targetId: string
  }) {
    if (diagramStore.type !== 'concept_map') return
    if (!llmResultsStore.selectedModel) return
    generateRelationship(payload.connectionId, payload.sourceId, payload.targetId)
  }

  function handleConceptMapLinkDragStart(payload: { sourceId: string }) {
    linkDragSourceId.value = payload.sourceId
    linkDragCursor.value = null
  }

  function handleConceptMapLinkDragEnd() {
    linkDragSourceId.value = null
    linkDragCursor.value = null
    linkDragTargetNodeId.value = null
  }

  const linkPreviewPath = computed(() => {
    if (!linkDragSourceId.value || !linkDragCursor.value || diagramStore.type !== 'concept_map')
      return null
    const nodes = diagramStore.data?.nodes ?? []
    const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
    if (!sourceNode?.position) return null
    const sourceCenter = getConceptNodeCenter(sourceNode)
    const cursor = linkDragCursor.value
    const targetNodeId = linkDragTargetNodeId.value
    const targetNode = targetNodeId ? nodes.find((n) => n.id === targetNodeId) : null
    let targetAtEdge: { x: number; y: number }
    let sourcePos: (typeof Position)[keyof typeof Position]
    let targetPos: (typeof Position)[keyof typeof Position]
    if (targetNode?.position) {
      const targetCenter = getConceptNodeCenter(targetNode)
      const dx = targetCenter.x - sourceCenter.x
      const dy = targetCenter.y - sourceCenter.y
      const positions = getPositionsFromAngle(dx, dy)
      sourcePos = positions.source
      targetPos = positions.target
      targetAtEdge = getConceptNodeEdgePoint(targetNode, targetPos)
    } else {
      const dx = cursor.x - sourceCenter.x
      const dy = cursor.y - sourceCenter.y
      const positions = getPositionsFromAngle(dx, dy)
      sourcePos = positions.source
      targetPos = positions.target
      targetAtEdge = getEdgePoint(cursor, targetPos, PILL_HALF_WIDTH, PILL_HALF_HEIGHT)
    }
    const [edgePath] = getBezierPath({
      sourceX: sourceCenter.x,
      sourceY: sourceCenter.y,
      sourcePosition: sourcePos,
      targetX: targetAtEdge.x,
      targetY: targetAtEdge.y,
      targetPosition: targetPos,
      curvature: 0.25,
    })
    return edgePath
  })

  const linkPreviewShowArrow = computed(() => {
    if (!linkDragSourceId.value || !linkDragCursor.value || diagramStore.type !== 'concept_map')
      return false
    const nodes = diagramStore.data?.nodes ?? []
    const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
    if (!sourceNode?.position) return false
    const sourceCenter = getConceptNodeCenter(sourceNode)
    const targetNodeId = linkDragTargetNodeId.value
    const targetNode = targetNodeId ? nodes.find((n) => n.id === targetNodeId) : null
    const targetCenter = targetNode?.position
      ? getConceptNodeCenter(targetNode)
      : linkDragCursor.value
    return targetCenter.y <= sourceCenter.y
  })

  function handleConceptMapDragOver(event: DragEvent) {
    if (diagramStore.type !== 'concept_map') return
    const types = event.dataTransfer?.types ?? []
    const hasLinkData = types.includes(CONCEPT_LINK_DATA_TYPE)
    const hasPaletteConcept = types.includes(PALETTE_CONCEPT_DRAG_MIME)
    if ((hasLinkData || hasPaletteConcept) && event.dataTransfer) {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
    }
    if (hasLinkData && linkDragSourceId.value) {
      const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
      linkDragCursor.value = { x: flowPos.x, y: flowPos.y }
      const nodeEl = (event.target as HTMLElement).closest('.vue-flow__node')
      const targetId = nodeEl?.getAttribute('data-id') ?? null
      linkDragTargetNodeId.value = targetId && targetId !== linkDragSourceId.value ? targetId : null
    }
  }

  function handleConceptMapDrop(event: DragEvent) {
    if (diagramStore.type !== 'concept_map') return

    const paletteData = event.dataTransfer?.getData(PALETTE_CONCEPT_DRAG_MIME)
    if (paletteData) {
      event.preventDefault()
      const target = event.target as HTMLElement
      if (target.closest('.vue-flow__node')) return
      try {
        const parsed = JSON.parse(paletteData) as {
          text: string
          relationship_label?: string
        }
        const text = parsed.text
        const rootLinkLabel = (parsed.relationship_label ?? '').trim()
        const flowPos = screenToFlowCoordinate({
          x: event.clientX,
          y: event.clientY,
        })
        diagramStore.addNode({
          id: '',
          text: text || t('diagram.defaultNewConcept'),
          type: 'branch',
          position: { x: flowPos.x - 50, y: flowPos.y - 18 },
        })
        const nodesAfter = diagramStore.data?.nodes ?? []
        const newId = nodesAfter[nodesAfter.length - 1]?.id
        const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)
        if (newId && rootId) {
          diagramStore.addConnection(rootId, newId, rootLinkLabel)
        }
        diagramStore.pushHistory(newId && rootId ? 'Add concept and link from root' : 'Add concept')
      } catch {
        // Ignore malformed palette data
      }
      return
    }

    const sourceId = event.dataTransfer?.getData(CONCEPT_LINK_DATA_TYPE)
    if (!sourceId) return

    const target = event.target as HTMLElement
    const nodeElement = target.closest('.vue-flow__node')
    if (nodeElement) {
      return
    }

    event.preventDefault()
    const flowPos = screenToFlowCoordinate({
      x: event.clientX,
      y: event.clientY,
    })
    diagramStore.addNode({
      id: '',
      text: t('diagram.defaultNewConcept'),
      type: 'branch',
      position: { x: flowPos.x - 50, y: flowPos.y - 18 },
    })
    const nodes = diagramStore.data?.nodes ?? []
    const newId = nodes[nodes.length - 1]?.id
    if (newId) {
      diagramStore.addConnection(sourceId, newId, '')
    }
    diagramStore.pushHistory('Add concept and link')
  }

  onMounted(() => {
    eventBus.on('concept_map:link_drop', handleConceptMapLinkDrop)
    eventBus.on('concept_map:label_cleared', handleConceptMapLabelCleared)
    eventBus.on('concept_map:link_drag_start', handleConceptMapLinkDragStart)
    eventBus.on('concept_map:link_drag_end', handleConceptMapLinkDragEnd)
  })

  onUnmounted(() => {
    eventBus.off('concept_map:link_drop', handleConceptMapLinkDrop)
    eventBus.off('concept_map:label_cleared', handleConceptMapLabelCleared)
    eventBus.off('concept_map:link_drag_start', handleConceptMapLinkDragStart)
    eventBus.off('concept_map:link_drag_end', handleConceptMapLinkDragEnd)
  })

  return {
    linkDragSourceId,
    linkDragCursor,
    linkDragTargetNodeId,
    linkPreviewPath,
    linkPreviewShowArrow,
    handleConceptMapDragOver,
    handleConceptMapDrop,
  }
}
