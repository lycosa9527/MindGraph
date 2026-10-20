import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import { DEFAULT_MINDMAP_RANK_SEPARATION } from '@/composables/diagrams/layoutConfig'
import { recalculateMindMapV2ColumnPositions } from '@/stores/diagram/mindMapLayout'
import { loadMindMapSpec } from '@/stores/specLoader/mindMap'
import type { Connection, DiagramNode } from '@/types'
import { mindMapAdornmentPathKey } from '@/utils/mindMapAdornments'
import { buildMindMapTreeChildrenMap, mindMapNodeSide } from '@/utils/mindMapLocation'
import {
  NODE_IMAGE_GAP,
  NODE_IMAGE_THUMB_HEIGHT,
  expandMindMapLayoutSizesForImages,
  mindMapImageFrameWidth,
  nodeIdsWithImage,
} from '@/utils/nodeImageFrame'

function node(id: string, x: number, y: number, width: number, height: number): DiagramNode {
  return {
    id,
    text: id,
    type: id === 'topic' ? 'topic' : 'branch',
    position: { x, y },
    data: { estimatedWidth: width, estimatedHeight: height },
  }
}

function pos(nodes: DiagramNode[], id: string): { x: number; y: number } {
  const found = nodes.find((item) => item.id === id)?.position
  if (!found) throw new Error(`missing ${id}`)
  return found
}

describe('mind map image layout', () => {
  const textWidth = 90
  const textHeight = 36
  const nodes: DiagramNode[] = [
    node('topic', 400, 200, 120, 40),
    node('branch-r-1-0', 560, 160, textWidth, textHeight),
    node('branch-r-1-1', 560, 220, textWidth, textHeight),
    node('branch-r-2-0', 700, 160, textWidth, textHeight),
  ]
  const connections: Connection[] = [
    { id: 'c0', source: 'topic', target: 'branch-r-1-0' },
    { id: 'c1', source: 'topic', target: 'branch-r-1-1' },
    { id: 'c2', source: 'branch-r-1-0', target: 'branch-r-2-0' },
  ]

  it('keeps a measured picture box instead of adding the frame again', () => {
    const sized = expandMindMapLayoutSizesForImages(
      nodes,
      { 'branch-r-1-0': 240 },
      { 'branch-r-1-0': 220 },
      new Set(['branch-r-1-0'])
    )
    expect(sized.nodeWidths['branch-r-1-0']).toBe(240)
    expect(sized.nodeHeights['branch-r-1-0']).toBe(220)

    const bare = node('branch-r-1-0', 0, 0, 90, 36)
    delete bare.data?.estimatedHeight
    delete bare.data?.estimatedWidth
    const measuredOnly = expandMindMapLayoutSizesForImages(
      [bare],
      { 'branch-r-1-0': 240 },
      { 'branch-r-1-0': 220 },
      new Set(['branch-r-1-0'])
    )
    expect(measuredOnly.nodeHeights['branch-r-1-0']).toBe(220)
    expect(measuredOnly.nodeWidths['branch-r-1-0']).toBe(240)
  })

  it('stacks the next sibling below the thumbnail and shifts children outward', () => {
    const plain = recalculateMindMapV2ColumnPositions(nodes, 120, {}, {}, connections)
    const withImage = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      {},
      connections,
      new Set(),
      null,
      { imageNodeIds: new Set(['branch-r-1-0']) }
    )

    const plainUpper = pos(plain.nodes, 'branch-r-1-0')
    const plainLower = pos(plain.nodes, 'branch-r-1-1')
    const imageUpper = pos(withImage.nodes, 'branch-r-1-0')
    const imageLower = pos(withImage.nodes, 'branch-r-1-1')
    const plainGap = plainLower.y - plainUpper.y
    const imageGap = imageLower.y - imageUpper.y
    expect(imageGap).toBeGreaterThanOrEqual(plainGap + NODE_IMAGE_THUMB_HEIGHT + NODE_IMAGE_GAP - 1)

    const child = pos(withImage.nodes, 'branch-r-2-0')
    const parent = pos(withImage.nodes, 'branch-r-1-0')
    expect(child.x).toBeGreaterThanOrEqual(
      parent.x + mindMapImageFrameWidth() + DEFAULT_MINDMAP_RANK_SEPARATION - 1
    )
  })

  it('does not grow a picture node past a larger measured height', () => {
    const measured = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      { 'branch-r-1-0': 220 },
      connections,
      new Set(),
      null,
      { imageNodeIds: new Set(['branch-r-1-0']) }
    )
    const sameHeight = recalculateMindMapV2ColumnPositions(
      nodes,
      120,
      {},
      { 'branch-r-1-0': 220 },
      connections
    )
    const measuredGap =
      pos(measured.nodes, 'branch-r-1-1').y - pos(measured.nodes, 'branch-r-1-0').y
    const plainGap =
      pos(sameHeight.nodes, 'branch-r-1-1').y - pos(sameHeight.nodes, 'branch-r-1-0').y
    expect(measuredGap).toBeCloseTo(plainGap, 0)
  })
})

type SavedNode = {
  id: string
  type?: string
  text?: string
  x?: number
  y?: number
  estimatedWidth?: number
  estimatedHeight?: number
  nodeShape?: string
}

type SavedMap = {
  id: string
  label: string
  nodeCount: number
  style?: string | null
  nodes: SavedNode[]
  connections: Connection[]
}

type SavedTree = {
  id: string
  topic: string
  children: unknown[]
}

type Box = { id: string; x: number; y: number; w: number; h: number }

function savedToNodes(saved: SavedNode[]): DiagramNode[] {
  return saved.map((item) => ({
    id: item.id,
    text: item.text || item.id,
    type: item.type === 'topic' || item.id === 'topic' ? 'topic' : 'branch',
    position: { x: item.x ?? 0, y: item.y ?? 0 },
    data: {
      estimatedWidth: item.estimatedWidth,
      estimatedHeight: item.estimatedHeight,
    },
    ...(item.nodeShape ? { style: { nodeShape: item.nodeShape } } : {}),
  }))
}

function layoutBoxes(
  nodes: DiagramNode[],
  connections: Connection[],
  imageNodeIds: ReadonlySet<string>,
  styleId?: string | null
): Box[] {
  const widths: Record<string, number> = {}
  const heights: Record<string, number> = {}
  for (const node of nodes) {
    const width = node.data?.estimatedWidth
    const height = node.data?.estimatedHeight
    if (typeof width === 'number' && width > 0) widths[node.id] = width
    if (typeof height === 'number' && height > 0) heights[node.id] = height
  }
  const sized = expandMindMapLayoutSizesForImages(nodes, widths, heights, imageNodeIds)
  const topicWidth = sized.nodeWidths.topic ?? widths.topic ?? null
  const laid = recalculateMindMapV2ColumnPositions(
    nodes,
    topicWidth,
    widths,
    heights,
    connections,
    new Set(),
    styleId,
    imageNodeIds.size > 0 ? { imageNodeIds } : undefined
  )
  return laid.nodes.map((node) => {
    const width =
      sized.nodeWidths[node.id] ??
      (typeof node.data?.estimatedWidth === 'number' ? node.data.estimatedWidth : 80)
    const height =
      sized.nodeHeights[node.id] ??
      (typeof node.data?.estimatedHeight === 'number' ? node.data.estimatedHeight : 36)
    return {
      id: node.id,
      x: node.position?.x ?? 0,
      y: node.position?.y ?? 0,
      w: width,
      h: height,
    }
  })
}

function assertImageClearsNeighbors(
  nodes: DiagramNode[],
  connections: Connection[],
  imageId: string,
  styleId?: string | null
): void {
  const boxes = layoutBoxes(nodes, connections, new Set([imageId]), styleId)
  const byId = new Map(boxes.map((box) => [box.id, box]))
  const image = byId.get(imageId)
  expect(image, imageId).toBeDefined()
  if (!image) return
  const children = buildMindMapTreeChildrenMap(connections)
  const gap = DEFAULT_MINDMAP_RANK_SEPARATION
  for (const [parentId, kids] of children) {
    if (parentId !== imageId) continue
    for (const kidId of kids) {
      const child = byId.get(kidId)
      const side = mindMapNodeSide(kidId, { nodes, connections })
      if (!child || !side) continue
      if (side === 'right') {
        expect(child.x).toBeGreaterThanOrEqual(image.x + image.w + gap - 1)
      } else {
        expect(child.x + child.w).toBeLessThanOrEqual(image.x - gap + 1)
      }
    }
  }
  const imageSide = mindMapNodeSide(imageId, { nodes, connections })
  for (const kids of children.values()) {
    if (!kids.includes(imageId) || kids.length < 2) continue
    const row = kids
      .filter((id) => mindMapNodeSide(id, { nodes, connections }) === imageSide)
      .map((id) => byId.get(id))
      .filter((box): box is Box => box != null)
      .sort((a, b) => a.y - b.y)
    for (let index = 1; index < row.length; index += 1) {
      const prev = row[index - 1]
      const next = row[index]
      if (!prev || !next) continue
      if (prev.id !== imageId && next.id !== imageId) continue
      expect(
        next.y,
        `${prev.id}@${prev.y}+${prev.h} overlaps ${next.id}@${next.y} image=${imageId}`
      ).toBeGreaterThanOrEqual(prev.y + prev.h - 0.5)
    }
  }
}

const fixturePath = process.env.PG_MINDMAP_LAYOUT_FIXTURE
const fixtureReady = Boolean(fixturePath && existsSync(fixturePath))

function loadPgMindMapFixture(): { maps: SavedMap[]; trees: SavedTree[] } {
  if (!fixturePath || !existsSync(fixturePath)) return { maps: [], trees: [] }
  return JSON.parse(readFileSync(fixturePath, 'utf8')) as {
    maps: SavedMap[]
    trees: SavedTree[]
  }
}

describe.skipIf(!fixtureReady)('real postgres mind maps', () => {
  const fixture = loadPgMindMapFixture()

  it('leaves room around a picture on saved canvas maps', () => {
    expect(fixture.maps.length).toBeGreaterThan(0)
    for (const map of fixture.maps) {
      const nodes = savedToNodes(map.nodes)
      const connections = map.connections
      const children = buildMindMapTreeChildrenMap(connections)
      const busy = [...children.entries()].find(
        ([id, kids]) =>
          id !== 'topic' && kids.length > 0 && (children.get('topic') ?? []).length > 1
      )
      const imageId = busy?.[0] ?? nodes.find((node) => node.id !== 'topic')?.id
      expect(imageId, map.id).toBeTruthy()
      if (!imageId) continue
      const pathKey = mindMapAdornmentPathKey(imageId, connections)
      const adornmentKey = pathKey ?? imageId
      const resolved = nodeIdsWithImage(
        nodes,
        { _mindmap_adornments: { [adornmentKey]: { imageUrl: 'data:image/png;base64,aa' } } },
        connections
      )
      expect(resolved.has(imageId), `${map.label} ${adornmentKey}`).toBe(true)
      assertImageClearsNeighbors(nodes, connections, imageId, map.style)
      assertImageClearsNeighbors(nodes, connections, 'topic', map.style)
    }
  })

  it('leaves room around a picture on saved tree specs', () => {
    expect(fixture.trees.length).toBeGreaterThan(0)
    for (const tree of fixture.trees) {
      const loaded = loadMindMapSpec(
        { topic: tree.topic, children: tree.children },
        { canvasMode: 'v2' }
      )
      const nodes = loaded.nodes
      const connections = loaded.connections
      const children = buildMindMapTreeChildrenMap(connections)
      const imageId =
        [...children.keys()].find((id) => id !== 'topic' && (children.get(id) ?? []).length > 0) ??
        nodes.find((node) => node.id !== 'topic')?.id
      expect(imageId, tree.id).toBeTruthy()
      if (!imageId) continue
      assertImageClearsNeighbors(nodes, connections, imageId, null)
    }
  })
})
