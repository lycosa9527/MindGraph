import { computed, ref, watch } from 'vue'

import { resetFormatBrushState } from '@/composables/canvasToolbar/useCanvasToolbarFormatting'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  computeMindMapAssociationHandles,
  mindMapAssociationSameSide,
  parseAssociationCurveOffset,
  type AssociationCurveOffset,
} from '@/utils/mindMapAssociationLine'
import {
  MIND_MAP_ASSOCIATION_EDGE_TYPE,
  isMindMapAssociationConnection,
} from '@/utils/mindMapLocation'

export const associationLineActive = ref(false)
export const associationLineSourceId = ref<string | null>(null)
export const associationLineCursor = ref<{ x: number; y: number } | null>(null)
export const associationLinePendingEditId = ref<string | null>(null)
export const associationLineHoverId = ref<string | null>(null)
export const associationLineToolbarId = ref<string | null>(null)
export const associationCurveDrag = ref<{
  id: string
  offset: { x: number; y: number }
} | null>(null)

const ASSOCIATION_HOVER_LEAVE_MS = 160
let associationHoverLeaveTimer: ReturnType<typeof setTimeout> | null = null

export function associationCurveOffsetForEdge(
  edgeId: string,
  stored: unknown
): AssociationCurveOffset | undefined {
  const live = associationCurveDrag.value
  if (live?.id === edgeId) return live.offset
  return parseAssociationCurveOffset(stored)
}

export function setAssociationLineHover(id: string | null): void {
  if (associationHoverLeaveTimer !== null) {
    clearTimeout(associationHoverLeaveTimer)
    associationHoverLeaveTimer = null
  }
  if (id) {
    associationLineHoverId.value = id
    return
  }
  associationHoverLeaveTimer = setTimeout(() => {
    associationLineHoverId.value = null
    associationHoverLeaveTimer = null
  }, ASSOCIATION_HOVER_LEAVE_MS)
}

let associationLineWatchBound = false
let associationLineEscapeBound = false
let associationLinePaneBound = false
let associationLinePointerBound = false
let associationLineToolbarPointerBound = false

function isAssociationToolbarEvent(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  return Boolean(
    target.closest('.mm-summary-toolbar') ||
      target.closest('.mm-summary-toolbar-popper') ||
      target.closest('.mm-summary-handle-btn') ||
      target.closest('.mg-association-delete')
  )
}

export function setAssociationLineToolbar(id: string | null): void {
  associationLineToolbarId.value = id
}
let toFlowCoordinate: ((pos: { x: number; y: number }) => { x: number; y: number }) | null = null

function nodeCenter(node: {
  position?: { x: number; y: number }
  data?: Record<string, unknown>
  style?: { width?: number; height?: number }
}): { x: number; y: number } | null {
  if (!node.position) return null
  const width = Number(node.data?.estimatedWidth) || Number(node.style?.width) || 120
  const height = Number(node.data?.estimatedHeight) || Number(node.style?.height) || 36
  return {
    x: node.position.x + width / 2,
    y: node.position.y + height / 2,
  }
}

function onAssociationPointerMove(event: PointerEvent): void {
  if (!associationLineActive.value || !toFlowCoordinate) return
  associationLineCursor.value = toFlowCoordinate({ x: event.clientX, y: event.clientY })
}

export function useMindMapAssociationLine(options?: {
  screenToFlowCoordinate?: (pos: { x: number; y: number }) => { x: number; y: number }
}) {
  const diagramStore = useDiagramSession()
  const { t } = useLanguage()
  const notify = useNotifications()

  if (options?.screenToFlowCoordinate) {
    toFlowCoordinate = options.screenToFlowCoordinate
  }

  const previewPath = computed(() => {
    if (!associationLineActive.value || !associationLineSourceId.value) return null
    const cursor = associationLineCursor.value
    if (!cursor) return null
    const node = diagramStore.data?.nodes?.find((n) => n.id === associationLineSourceId.value)
    if (!node) return null
    const start = nodeCenter(node)
    if (!start) return null
    return `M ${start.x} ${start.y} L ${cursor.x} ${cursor.y}`
  })

  function deactivate(): void {
    associationLineActive.value = false
    associationLineSourceId.value = null
    associationLineCursor.value = null
    if (typeof document !== 'undefined') {
      document.documentElement.classList.remove('mg-association-line-active')
    }
  }

  function connectNodes(sourceId: string, targetId: string): boolean {
    if (sourceId === targetId) return false
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    if (!mindMapAssociationSameSide(sourceId, targetId, { nodes, connections })) {
      notify.warning(
        t('canvas.ribbon.assocLineSameSide', 'Relationship lines stay on the same side')
      )
      return false
    }
    const existing = connections.find(
      (c) =>
        isMindMapAssociationConnection(c) &&
        ((c.source === sourceId && c.target === targetId) ||
          (c.source === targetId && c.target === sourceId))
    )
    if (existing) {
      associationLinePendingEditId.value = existing.id
      diagramStore.selectConnection(existing.id)
      deactivate()
      return true
    }
    const sourceNode = nodes.find((n) => n.id === sourceId)
    const targetNode = nodes.find((n) => n.id === targetId)
    if (!sourceNode || !targetNode) {
      notify.warning(t('canvas.ribbon.selectTwoNodes'))
      return false
    }
    diagramStore.pushHistory(t('canvas.ribbon.assocLine'))
    const extra = {
      edgeType: MIND_MAP_ASSOCIATION_EDGE_TYPE,
      style: { strokeColor: '#64748b', strokeWidth: 2, strokeDasharray: '6 4' },
      ...computeMindMapAssociationHandles(sourceNode, targetNode, { nodes, connections }),
    }
    const created =
      diagramStore.addConnection(sourceId, targetId, '', extra) ||
      diagramStore.addConnection(targetId, sourceId, '', {
        ...extra,
        ...computeMindMapAssociationHandles(targetNode, sourceNode, { nodes, connections }),
      })
    if (!created) {
      notify.warning(t('canvas.ribbon.selectTwoNodes'))
      return false
    }
    associationLinePendingEditId.value = created
    diagramStore.selectConnection(created)
    deactivate()
    return true
  }

  function startFromSelection(): void {
    const ids = diagramStore.selectedNodes.filter((id, index, list) => list.indexOf(id) === index)
    if (ids.length === 0) {
      notify.warning(t('canvas.toolbar.selectNodesFirst'))
      return
    }
    resetFormatBrushState()
    if (ids.length >= 2) {
      connectNodes(ids[0], ids[1])
      return
    }
    associationLineSourceId.value = ids[0]
    associationLineActive.value = true
    if (typeof document !== 'undefined') {
      document.documentElement.classList.add('mg-association-line-active')
    }
    notify.success(t('canvas.ribbon.assocLineHint'))
  }

  if (!associationLineWatchBound) {
    associationLineWatchBound = true
    watch(
      () => diagramStore.selectedNodes.join('\0'),
      (joined) => {
        if (associationLineToolbarId.value && joined) {
          associationLineToolbarId.value = null
        }
        if (!associationLineActive.value || !associationLineSourceId.value) return
        const ids = joined ? joined.split('\0') : []
        const target = ids.find((id) => id && id !== associationLineSourceId.value)
        if (!target) return
        connectNodes(associationLineSourceId.value, target)
      }
    )
  }

  if (!associationLineEscapeBound && typeof document !== 'undefined') {
    associationLineEscapeBound = true
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return
      if (associationCurveDrag.value) {
        associationCurveDrag.value = null
        return
      }
      if (associationLineToolbarId.value) {
        associationLineToolbarId.value = null
        return
      }
      if (!associationLineActive.value) return
      deactivate()
    })
  }

  if (!associationLinePaneBound) {
    associationLinePaneBound = true
    eventBus.on('canvas:pane_clicked', () => {
      associationLineToolbarId.value = null
      if (!associationLineActive.value) return
      deactivate()
    })
  }

  if (!associationLineToolbarPointerBound && typeof document !== 'undefined') {
    associationLineToolbarPointerBound = true
    document.addEventListener(
      'pointerdown',
      (event) => {
        if (!associationLineToolbarId.value) return
        if (isAssociationToolbarEvent(event.target)) return
        associationLineToolbarId.value = null
      },
      true
    )
  }

  if (!associationLinePointerBound && typeof document !== 'undefined') {
    associationLinePointerBound = true
    document.addEventListener('pointermove', onAssociationPointerMove)
  }

  return {
    associationLineActive,
    associationLineCursor,
    previewPath,
    startFromSelection,
    cancel: deactivate,
  }
}
