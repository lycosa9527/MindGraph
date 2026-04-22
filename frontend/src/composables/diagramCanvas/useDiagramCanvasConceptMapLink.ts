import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { Position, getBezierPath } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import {
  CONCEPT_LINK_DATA_TYPE,
  CONCEPT_LINK_FROM_RELATIONSHIP_TYPE,
  type RelationshipLinkDragPayload,
} from '@/composables/diagramCanvas/conceptMapLinkMime'
import { PALETTE_CONCEPT_DRAG_MIME } from '@/composables/nodePalette/constants'
import { useDiagramStore, useLLMResultsStore } from '@/stores'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

import {
  PILL_HALF_HEIGHT,
  PILL_HALF_WIDTH,
  getConceptNodeCenter,
  getConceptNodeEdgePoint,
  getEdgePoint,
  pickAnchorNodeIdForRelationshipToExistingNode,
  pickAnchorNodeIdForRelationshipToNewConcept,
  getPositionsFromAngle,
} from './conceptMapLinkPreviewGeometry'

type DiagramStore = ReturnType<typeof useDiagramStore>

type LinkRelationshipOrigin = {
  labelX: number
  labelY: number
  relSource: string
  relTarget: string
}

function buildConceptLinkPreviewPath(
  sourceCenter: { x: number; y: number },
  cursor: { x: number; y: number },
  targetNodeId: string | null,
  nodes: Array<{
    id: string
    position?: { x: number; y: number }
    data?: { nodeType?: string }
    type?: string
  }>
): string {
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
}

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
  const linkDragFromRelationship = ref<LinkRelationshipOrigin | null>(null)
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

  function handleConceptMapLinkDrop(payload: {
    sourceId: string
    targetId: string
    linkedFromConnectionId?: string
  }) {
    if (diagramStore.type !== 'concept_map') return
    const extra = payload.linkedFromConnectionId
      ? {
          linkedFromConnectionId: payload.linkedFromConnectionId,
          arrowheadDirection: 'target' as const,
          arrowheadLocked: true,
        }
      : undefined
    const connId = diagramStore.addConnection(payload.sourceId, payload.targetId, '', extra)
    if (connId) {
      diagramStore.pushHistory('Add link')
    }
    if (!payload.linkedFromConnectionId && llmResultsStore.selectedModel) {
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

  function handleConceptMapLinkDragStart(payload: {
    sourceId?: string
    connectionId?: string
    labelX?: number
    labelY?: number
    relSource?: string
    relTarget?: string
  }) {
    if (
      payload.labelX != null &&
      payload.labelY != null &&
      payload.relSource &&
      payload.relTarget
    ) {
      linkDragFromRelationship.value = {
        labelX: payload.labelX,
        labelY: payload.labelY,
        relSource: payload.relSource,
        relTarget: payload.relTarget,
      }
      linkDragSourceId.value = null
    } else {
      linkDragFromRelationship.value = null
      linkDragSourceId.value = payload.sourceId ?? null
    }
    linkDragCursor.value = null
    linkDragTargetNodeId.value = null
  }

  function handleConceptMapLinkDragEnd() {
    linkDragSourceId.value = null
    linkDragFromRelationship.value = null
    linkDragCursor.value = null
    linkDragTargetNodeId.value = null
  }

  const linkPreviewPath = computed(() => {
    if (!linkDragCursor.value || diagramStore.type !== 'concept_map') return null
    const nodes = (diagramStore.data?.nodes ?? []) as Array<{
      id: string
      position?: { x: number; y: number }
      data?: { nodeType?: string }
      type?: string
    }>
    const rel = linkDragFromRelationship.value
    if (rel) {
      return buildConceptLinkPreviewPath(
        { x: rel.labelX, y: rel.labelY },
        linkDragCursor.value,
        linkDragTargetNodeId.value,
        nodes
      )
    }
    if (!linkDragSourceId.value) return null
    const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
    if (!sourceNode?.position) return null
    const sourceCenter = getConceptNodeCenter(sourceNode)
    return buildConceptLinkPreviewPath(
      sourceCenter,
      linkDragCursor.value,
      linkDragTargetNodeId.value,
      nodes
    )
  })

  const linkPreviewShowArrow = computed(() => {
    if (!linkDragCursor.value || diagramStore.type !== 'concept_map') return false
    const rel = linkDragFromRelationship.value
    const startY = rel
      ? rel.labelY
      : (() => {
          const nodes = diagramStore.data?.nodes ?? []
          const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
          if (!sourceNode?.position) return null
          return getConceptNodeCenter(sourceNode).y
        })()
    if (startY == null) return false
    const targetNodeId = linkDragTargetNodeId.value
    const targetNode = targetNodeId
      ? (diagramStore.data?.nodes ?? []).find((n) => n.id === targetNodeId)
      : null
    const targetCenterY = targetNode?.position
      ? getConceptNodeCenter(targetNode).y
      : linkDragCursor.value.y
    return targetCenterY <= startY
  })

  function handleConceptMapDragOver(event: DragEvent) {
    if (diagramStore.type !== 'concept_map') return
    const types = event.dataTransfer?.types ?? []
    const hasNodeLink = types.includes(CONCEPT_LINK_DATA_TYPE)
    const hasRelLink = types.includes(CONCEPT_LINK_FROM_RELATIONSHIP_TYPE)
    const hasLinkData = hasNodeLink || hasRelLink
    const hasPaletteConcept = types.includes(PALETTE_CONCEPT_DRAG_MIME)
    if ((hasLinkData || hasPaletteConcept) && event.dataTransfer) {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
    }
    if (
      hasLinkData &&
      (linkDragSourceId.value || linkDragFromRelationship.value) &&
      event.dataTransfer
    ) {
      const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
      linkDragCursor.value = { x: flowPos.x, y: flowPos.y }
      const nodeEl = (event.target as HTMLElement).closest('.vue-flow__node')
      const targetId = nodeEl?.getAttribute('data-id') ?? null
      if (linkDragFromRelationship.value) {
        linkDragTargetNodeId.value = targetId
        return
      }
      linkDragTargetNodeId.value =
        targetId && targetId !== linkDragSourceId.value ? targetId : null
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

    const relJson = event.dataTransfer?.getData(CONCEPT_LINK_FROM_RELATIONSHIP_TYPE)
    if (relJson) {
      const target = event.target as HTMLElement
      if (target.closest('.vue-flow__node')) {
        return
      }
      event.preventDefault()
      const flowPos = screenToFlowCoordinate({
        x: event.clientX,
        y: event.clientY,
      })
      let parsed: RelationshipLinkDragPayload
      try {
        parsed = JSON.parse(relJson) as RelationshipLinkDragPayload
      } catch {
        return
      }
      diagramStore.addNode({
        id: '',
        text: t('diagram.defaultNewConcept'),
        type: 'branch',
        position: { x: flowPos.x - 50, y: flowPos.y - 18 },
      })
      const nodes = diagramStore.data?.nodes ?? []
      const newId = nodes[nodes.length - 1]?.id
      const newNode = newId ? nodes.find((n) => n.id === newId) : null
      if (newId && newNode) {
        const getNode = (id: string) => diagramStore.data?.nodes?.find((n) => n.id === id)
        const anchor = pickAnchorNodeIdForRelationshipToNewConcept(
          newNode,
          parsed.sourceNodeId,
          parsed.targetNodeId,
          (id) => getNode(id)
        )
        const connId = diagramStore.addConnection(anchor, newId, '', {
          linkedFromConnectionId: parsed.connectionId,
          arrowheadDirection: 'target',
          arrowheadLocked: true,
        })
        if (connId) {
          diagramStore.pushHistory('Add link from relationship')
        }
      } else {
        diagramStore.pushHistory('Add concept')
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
