import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  associationLineHoverId,
  setAssociationLineHover,
} from '@/composables/mindMap/useMindMapAssociationLine'
import { recalculateMindMapV2ColumnPositions } from '@/stores/diagram/mindMapLayout'
import { buildMindMapChildrenMapByConnectionOrder } from '@/stores/diagram/mindMapStylePreservation'
import type { Connection, DiagramNode } from '@/types'
import { pointOnCubicBezierPath } from '@/utils/bezierSplit'
import {
  classicMindMapTopicSideConnections,
  withClassicMindMapTopicSourceHandle,
} from '@/utils/classicMindMapTopicHandles'
import {
  mindMapConnectionAnchorY,
  mindMapTextCenterAnchorY,
} from '@/config/mindMapGeometry'
import {
  applyAssociationChromePatch,
  associationArrowheadFromEnds,
  associationChromePointAwayFromLabel,
  associationCurveOffsetFromApex,
  computeMindMapAssociationHandles,
  mindMapAssociationCurveFromEnds,
  mindMapAssociationCurvePath,
  mindMapAssociationSameSide,
  snapMindMapAssociationEndpoint,
  withMindMapAssociationHandles,
} from '@/utils/mindMapAssociationLine'
import {
  MIND_MAP_ASSOCIATION_EDGE_TYPE,
  isMindMapAssociationConnection,
  mindMapTreeParentId,
} from '@/utils/mindMapLocation'

function branch(
  id: string,
  side: 'left' | 'right',
  x: number,
  y = 0
): DiagramNode {
  return {
    id,
    text: id,
    type: 'branch',
    position: { x, y },
    data: { mindMapSide: side, estimatedWidth: 80 },
  }
}

describe('mind map association connections', () => {
  const tree: Connection = { id: 'e1', source: 'topic', target: 'a' }
  const assoc: Connection = {
    id: 'assoc-1',
    source: 'a',
    target: 'b',
    edgeType: MIND_MAP_ASSOCIATION_EDGE_TYPE,
    label: 'leads to',
  }

  it('does not treat association overlays as tree parents', () => {
    expect(isMindMapAssociationConnection(assoc)).toBe(true)
    expect(mindMapTreeParentId([tree, assoc], 'a')).toBe('topic')
    expect(mindMapTreeParentId([tree, assoc], 'b')).toBeNull()
  })

  it('keeps association edges out of the children map', () => {
    const map = buildMindMapChildrenMapByConnectionOrder([tree, assoc])
    expect(map.get('topic')).toEqual(['a'])
    expect(map.get('a')).toBeUndefined()
  })

  it('lays out sibling topics before adapting an association overlay', () => {
    const topic: DiagramNode = {
      id: 'topic',
      text: 'topic',
      type: 'topic',
      position: { x: 400, y: 0 },
      data: { estimatedHeight: 40, estimatedWidth: 120 },
    }
    const left = (
      id: string,
      depth: number,
      y: number
    ): DiagramNode => ({
      id,
      text: id,
      type: 'branch',
      position: { x: depth === 1 ? 200 : 80, y },
      data: {
        mindMapSide: 'left',
        mindMapDepth: depth,
        estimatedHeight: 40,
        estimatedWidth: 80,
      },
    })
    const nodes: DiagramNode[] = [
      topic,
      left('branch-l-1-0', 1, -80),
      left('branch-l-2-1', 2, -140),
      left('branch-l-2-2', 2, -80),
      left('branch-l-1-3', 1, 80),
      left('branch-l-2-4', 2, 50),
      left('branch-l-2-5', 2, 110),
    ]
    const treeEdges: Connection[] = [
      { id: 't4', source: 'topic', target: 'branch-l-1-0' },
      { id: 't3', source: 'topic', target: 'branch-l-1-3' },
      { id: 'c41', source: 'branch-l-1-0', target: 'branch-l-2-1' },
      { id: 'c42', source: 'branch-l-1-0', target: 'branch-l-2-2' },
      { id: 'c31', source: 'branch-l-1-3', target: 'branch-l-2-4' },
      { id: 'c32', source: 'branch-l-1-3', target: 'branch-l-2-5' },
    ]
    const overlay: Connection = {
      id: 'assoc-curve',
      source: 'branch-l-2-1',
      target: 'branch-l-2-5',
      edgeType: MIND_MAP_ASSOCIATION_EDGE_TYPE,
    }
    const heights = Object.fromEntries(nodes.map((node) => [node.id, 40]))
    const siblingGap = (laid: DiagramNode[], upperId: string, lowerId: string): number => {
      const upper = laid.find((node) => node.id === upperId)
      const lower = laid.find((node) => node.id === lowerId)
      return (lower?.position?.y ?? 0) - ((upper?.position?.y ?? 0) + 40)
    }

    const packed = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      treeEdges,
      new Set(),
      'underline'
    )
    const withOverlay = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      heights,
      [...treeEdges, overlay],
      new Set(),
      'underline'
    )

    const packedGap = siblingGap(packed.nodes, 'branch-l-2-1', 'branch-l-2-2')
    const overlayGap = siblingGap(withOverlay.nodes, 'branch-l-2-1', 'branch-l-2-2')
    const otherGap = siblingGap(withOverlay.nodes, 'branch-l-2-4', 'branch-l-2-5')
    expect(overlayGap).toBeCloseTo(packedGap, 5)
    expect(overlayGap).toBeCloseTo(otherGap, 5)
    expect(overlayGap).toBeLessThan(40)
  })

  it('uses the outer left handle on both ends for left-side branches', () => {
    const leftOuter = branch('l-outer', 'left', -400, 0)
    const leftInner = branch('l-inner', 'left', -200, 80)
    const handles = computeMindMapAssociationHandles(leftOuter, leftInner)
    expect(handles.sourcePosition).toBe('left')
    expect(handles.targetPosition).toBe('left')
    expect(handles.sourceHandle).toBe('left-source')
    expect(handles.targetHandle).toBe('left')
  })

  it('keeps left→left when the target sits further left', () => {
    const leftInner = branch('l-inner', 'left', -200, 0)
    const leftOuter = branch('l-outer', 'left', -400, 80)
    const handles = computeMindMapAssociationHandles(leftInner, leftOuter)
    expect(handles.sourcePosition).toBe('left')
    expect(handles.targetPosition).toBe('left')
    expect(handles.sourceHandle).toBe('left-source')
    expect(handles.targetHandle).toBe('left')
  })

  it('uses the outer right handle on both ends for right-side branches', () => {
    const a = branch('r1', 'right', 240, 0)
    const b = branch('r2', 'right', 400, 80)
    const handles = computeMindMapAssociationHandles(a, b)
    expect(handles.sourcePosition).toBe('right')
    expect(handles.targetPosition).toBe('right')
    expect(handles.sourceHandle).toBe('right')
    expect(handles.targetHandle).toBe('right-target')
  })

  it('uses topic left/right handle ids when the center is an endpoint', () => {
    const topic: DiagramNode = {
      id: 'topic',
      text: '中心',
      type: 'topic',
      position: { x: 0, y: 0 },
      data: { estimatedWidth: 140 },
    }
    const rightNode = branch('r1', 'right', 240, 0)
    const handles = computeMindMapAssociationHandles(topic, rightNode)
    expect(handles.sourceHandle).toBe('mindmap-right')
    expect(handles.targetHandle).toBe('right-target')
  })

  it('allows same-side branches and rejects opposite sides', () => {
    const nodes = [
      branch('l1', 'left', -240, 0),
      branch('l2', 'left', -240, 80),
      branch('r1', 'right', 240, 0),
    ]
    const connections: Connection[] = [
      { id: 'e-l1', source: 'topic', target: 'l1', sourceHandle: 'mindmap-left' },
      { id: 'e-l2', source: 'topic', target: 'l2', sourceHandle: 'mindmap-left' },
      { id: 'e-r1', source: 'topic', target: 'r1', sourceHandle: 'mindmap-right' },
    ]
    const options = { nodes, connections }
    expect(mindMapAssociationSameSide('l1', 'l2', options)).toBe(true)
    expect(mindMapAssociationSameSide('l1', 'r1', options)).toBe(false)
    expect(mindMapAssociationSameSide('topic', 'l1', options)).toBe(true)
  })

  it('stamps left/right handles onto an association connection', () => {
    const nodes = [branch('a', 'left', -320, 0), branch('b', 'left', -160, 40)]
    const stamped = withMindMapAssociationHandles(assoc, nodes)
    expect(stamped.sourcePosition).toBe('left')
    expect(stamped.targetPosition).toBe('left')
    expect(stamped.sourceHandle).toBe('left-source')
    expect(stamped.targetHandle).toBe('left')
  })

  it('keeps association topic links out of classic side handle layout', () => {
    const nodes = [branch('a', 'left', -240, 0)]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a', sourceHandle: 'mindmap-left-0' },
      { id: 'assoc-topic', source: 'topic', target: 'a', edgeType: MIND_MAP_ASSOCIATION_EDGE_TYPE },
    ]
    expect(classicMindMapTopicSideConnections(connections, 'l', nodes)).toHaveLength(1)
    expect(
      withClassicMindMapTopicSourceHandle(connections[1], connections, nodes).sourceHandle
    ).toBeUndefined()
  })

  it('maps start/end arrow toggles onto arrowheadDirection', () => {
    expect(associationArrowheadFromEnds(false, true)).toBe('target')
    expect(associationArrowheadFromEnds(true, true)).toBe('both')
    expect(associationArrowheadFromEnds(false, false)).toBe('none')
  })

  it('applies dashed stroke and end arrow onto an association connection', () => {
    const next = applyAssociationChromePatch(
      { ...assoc, style: { strokeColor: '#64748b', strokeWidth: 2 } },
      { lineStyle: 'dashed', strokeWidth: 3, arrowheadDirection: 'target' }
    )
    expect(next.style?.strokeWidth).toBe(3)
    expect(next.style?.strokeDasharray).toMatch(/\d/)
    expect(next.style?.strokeDasharray).not.toBe('none')
    expect(next.arrowheadDirection).toBe('target')
  })

  it('snaps underline association Y to the text center, not the bar', () => {
    const height = 28
    const node: DiagramNode = {
      id: 'l1',
      text: '子项',
      type: 'branch',
      position: { x: 0, y: 100 },
      data: { estimatedHeight: height, style: { nodeShape: 'underline' } },
      style: { nodeShape: 'underline' },
    }
    const barY = mindMapConnectionAnchorY(100, height, 'underline')
    const textY = mindMapTextCenterAnchorY(100, height, 'underline')
    const snapped = snapMindMapAssociationEndpoint(
      node,
      { x: 40, y: barY },
      { measuredHeight: height }
    )
    expect(snapped.x).toBe(40)
    expect(snapped.y).toBe(textY)
    expect(snapped.y).toBeLessThan(barY)
  })

  it('keeps boxed-node association Y on the box midline', () => {
    const node: DiagramNode = {
      id: 'r1',
      text: '分支',
      type: 'branch',
      position: { x: 200, y: 80 },
      style: { nodeShape: 'rounded' },
    }
    const midY = mindMapTextCenterAnchorY(80, 36, 'rounded')
    expect(snapMindMapAssociationEndpoint(node, { x: 200, y: 99 }, { measuredHeight: 36 })).toEqual({
      x: 200,
      y: midY,
    })
  })

  it('routes the association curve from text-center Y', () => {
    const source: DiagramNode = {
      id: 'a',
      text: 'a',
      type: 'branch',
      position: { x: 0, y: 100 },
      style: { nodeShape: 'underline' },
    }
    const target: DiagramNode = {
      id: 'b',
      text: 'b',
      type: 'branch',
      position: { x: 0, y: 180 },
      style: { nodeShape: 'underline' },
    }
    const curve = mindMapAssociationCurveFromEnds(
      { x: 0, y: 127 },
      { x: 0, y: 207 },
      'left',
      source,
      target,
      { sourceHeight: 28, targetHeight: 28 }
    )
    const sourceY = mindMapTextCenterAnchorY(100, 28, 'underline')
    const targetY = mindMapTextCenterAnchorY(180, 28, 'underline')
    expect(curve.edgePath).toBe(
      mindMapAssociationCurvePath(0, sourceY, 0, targetY, 'left').edgePath
    )
  })

  it('bows left as a cubic, never a vertical straight, when ends share X', () => {
    const curve = mindMapAssociationCurvePath(100, 40, 100, 200, 'left')
    expect(curve.edgePath.startsWith('M100,40 C')).toBe(true)
    expect(curve.edgePath.includes(' L')).toBe(false)
    const controlX = Number(curve.edgePath.split('C')[1]?.split(',')[0])
    expect(controlX).toBeLessThan(100)
    expect(curve.labelX).toBeLessThan(100)
  })

  it('bows right as a cubic for right-side endpoints', () => {
    const curve = mindMapAssociationCurvePath(300, 40, 320, 180, 'right')
    const controlX = Number(curve.edgePath.split('C')[1]?.split(',')[0])
    expect(controlX).toBeGreaterThan(320)
    expect(curve.edgePath.includes(' L')).toBe(false)
  })

  it('routes a dragged apex through midpoint + offset', () => {
    const offset = associationCurveOffsetFromApex(
      { x: 0, y: 0 },
      { x: 0, y: 100 },
      { x: -80, y: 40 }
    )
    expect(offset).toEqual({ x: -80, y: -10 })
    const curve = mindMapAssociationCurvePath(0, 0, 0, 100, 'left', offset)
    const atMid = pointOnCubicBezierPath(curve.edgePath, 0.5)
    expect(atMid?.x).toBeCloseTo(-80)
    expect(atMid?.y).toBeCloseTo(40)
    expect(curve.labelX).toBeCloseTo(-80)
    expect(curve.labelY).toBeCloseTo(40)
  })

  it('persists curveOffset on a chrome patch', () => {
    const next = applyAssociationChromePatch(
      { ...assoc, style: { strokeColor: '#64748b', strokeWidth: 2 } },
      { curveOffset: { x: -48, y: 12 } }
    )
    expect(next.curveOffset).toEqual({ x: -48, y: 12 })
  })

  it('keeps chrome controls off the midpoint label', () => {
    const curve = mindMapAssociationCurvePath(0, 40, 0, 200, 'left')
    const label = { x: curve.labelX, y: curve.labelY }
    const handle = associationChromePointAwayFromLabel(curve.edgePath, label, 0.28, 48)
    const dist = Math.hypot(handle.x - label.x, handle.y - label.y)
    expect(dist).toBeGreaterThanOrEqual(48)
  })

  it('places the delete control on the cubic path, not above the label', () => {
    const mid = pointOnCubicBezierPath('M0,0 C0,0 10,10 10,10', 0.5)
    const early = pointOnCubicBezierPath('M0,0 C0,0 10,10 10,10', 0.28)
    expect(mid).toEqual({ x: 5, y: 5 })
    expect(early).not.toEqual(mid)
    expect(early?.y).toBeGreaterThan(0)
    expect(early?.y).toBeLessThan(5)
  })

  it('keeps the hover delete target until the leave delay elapses', () => {
    vi.useFakeTimers()
    setAssociationLineHover('assoc-1')
    expect(associationLineHoverId.value).toBe('assoc-1')
    setAssociationLineHover(null)
    expect(associationLineHoverId.value).toBe('assoc-1')
    vi.advanceTimersByTime(160)
    expect(associationLineHoverId.value).toBeNull()
    vi.useRealTimers()
  })
})

afterEach(() => {
  associationLineHoverId.value = null
  vi.useRealTimers()
})
