/**
 * Brace map layout after a part is added (AI brainstorm / node palette).
 * Positions must land on the live node ids, and the whole stays in the parts column.
 */
import { describe, expect, it } from 'vitest'

import { loadSpecForDiagramType } from '@/stores/specLoader'
import { recalculateBraceMapLayout } from '@/stores/specLoader/braceMap'
import type { Connection, DiagramNode } from '@/types'
import {
  BRACE_MAP_UID_DATA_KEY,
  isLeftoverBraceMapId,
  takeBraceMapStableId,
} from '@/utils/braceMapIdentity'

function node(id: string, text: string, type: DiagramNode['type'], x = 0, y = 0): DiagramNode {
  return { id, text, type, position: { x, y } }
}

function edge(source: string, target: string): Connection {
  return { id: `e-${source}-${target}`, source, target }
}

function positionOf(nodes: DiagramNode[], id: string): { x: number; y: number } {
  const position = nodes.find((n) => n.id === id)?.position
  if (!position) throw new Error(`missing ${id}`)
  return position
}

describe('recalculateBraceMapLayout', () => {
  it('places a brainstormed part beside the whole instead of stacking it on the origin', () => {
    const nodes: DiagramNode[] = [
      node('brace-whole', '手机', 'topic', 40, 180),
      node('part-cpu', '处理器', 'brace', 9000, 9000),
      node('sub-cpu-1', '子部分1.1', 'brace', 9000, 9000),
      node('sub-cpu-2', '子部分1.2', 'brace', 9000, 9000),
      node('part-mem', '内存', 'brace', 9000, 9000),
      node('sub-mem-1', '子部分2.1', 'brace', 9000, 9000),
      node('sub-mem-2', '子部分2.2', 'brace', 9000, 9000),
      node('part-cam', '图像传感器', 'brace', 9000, 9000),
      node('sub-cam-1', '子部分3.1', 'brace', 9000, 9000),
      node('sub-cam-2', '子部分3.2', 'brace', 9000, 9000),
      node('part-compute', '运算模块', 'brace', 0, 0),
      node('sub-compute-1', '新子部分 1', 'brace', 0, 0),
      node('sub-compute-2', '新子部分 2', 'brace', 0, 0),
      node('dimension-label', '功能模块', 'label', 40, 240),
    ]
    const connections: Connection[] = [
      edge('brace-whole', 'part-cpu'),
      edge('part-cpu', 'sub-cpu-1'),
      edge('part-cpu', 'sub-cpu-2'),
      edge('brace-whole', 'part-mem'),
      edge('part-mem', 'sub-mem-1'),
      edge('part-mem', 'sub-mem-2'),
      edge('brace-whole', 'part-cam'),
      edge('part-cam', 'sub-cam-1'),
      edge('part-cam', 'sub-cam-2'),
      edge('brace-whole', 'part-compute'),
      edge('part-compute', 'sub-compute-1'),
      edge('part-compute', 'sub-compute-2'),
    ]

    const laidOut = recalculateBraceMapLayout(nodes, connections)
    const again = recalculateBraceMapLayout(laidOut, connections)

    const whole = positionOf(again, 'brace-whole')
    const compute = positionOf(again, 'part-compute')
    const sub1 = positionOf(again, 'sub-compute-1')
    const sub2 = positionOf(again, 'sub-compute-2')
    const cpu = positionOf(again, 'part-cpu')
    const cam = positionOf(again, 'part-cam')
    const label = positionOf(again, 'dimension-label')

    expect(compute.x).toBeGreaterThan(whole.x)
    expect(sub1.x).toBeGreaterThan(compute.x)
    expect(sub1.y).not.toBe(sub2.y)
    expect(compute.y).toBeGreaterThan(cpu.y)
    expect(compute.y).toBeGreaterThan(cam.y)

    const firstPartTop = Math.min(cpu.y, cam.y, compute.y)
    const lastPartTop = Math.max(cpu.y, cam.y, compute.y)
    expect(whole.y).toBeGreaterThan(firstPartTop)
    expect(whole.y).toBeLessThan(lastPartTop)
    expect(label.y).toBeGreaterThan(whole.y)
  })

  it('keeps minted dual ids when a brainstormed part is laid out', () => {
    const loaded = loadSpecForDiagramType(
      {
        whole: '手机',
        dimension: '功能模块',
        parts: [
          { name: '处理器', subparts: [{ name: '子部分1.1' }, { name: '子部分1.2' }] },
          { name: '内存', subparts: [{ name: '子部分2.1' }, { name: '子部分2.2' }] },
          { name: '图像传感器', subparts: [{ name: '子部分3.1' }, { name: '子部分3.2' }] },
        ],
      },
      'brace_map'
    )
    const beforeIds = loaded.nodes.map((n) => n.id)
    expect(
      beforeIds
        .filter((id) => id !== 'brace-whole' && id !== 'dimension-label')
        .every((id) => !isLeftoverBraceMapId(id))
    ).toBe(true)
    for (const node of loaded.nodes) {
      if (node.type !== 'brace') continue
      expect(node.data?.[BRACE_MAP_UID_DATA_KEY]).toBe(node.id)
    }

    const claimed = new Set(beforeIds)
    const partId = takeBraceMapStableId(claimed)
    const sub1Id = takeBraceMapStableId(claimed)
    const sub2Id = takeBraceMapStableId(claimed)
    const nodes: DiagramNode[] = [
      ...loaded.nodes.map((n) => ({ ...n, position: { x: 0, y: 0 } })),
      node(partId, '运算模块', 'brace', 0, 0),
      node(sub1Id, '新子部分 1', 'brace', 0, 0),
      node(sub2Id, '新子部分 2', 'brace', 0, 0),
    ]
    const connections: Connection[] = [
      ...(loaded.connections ?? []),
      edge('brace-whole', partId),
      edge(partId, sub1Id),
      edge(partId, sub2Id),
    ]

    const laidOut = recalculateBraceMapLayout(nodes, connections)
    const laidOutIds = laidOut.map((n) => n.id)
    expect(new Set(laidOutIds).size).toBe(laidOutIds.length)
    for (const id of beforeIds) {
      expect(laidOutIds).toContain(id)
    }
    expect(laidOutIds).toContain(partId)

    const whole = positionOf(laidOut, 'brace-whole')
    const compute = positionOf(laidOut, partId)
    const sub1 = positionOf(laidOut, sub1Id)
    const sub2 = positionOf(laidOut, sub2Id)
    expect(compute.x).toBeGreaterThan(whole.x)
    expect(sub1.x).toBeGreaterThan(compute.x)
    expect(sub1.y).not.toBe(sub2.y)
    expect(compute.x).not.toBe(0)
    expect(sub1.y).not.toBe(sub2.y)
  })

  it('keeps the whole inside a column when the last part has more subparts', () => {
    const nodes: DiagramNode[] = [
      node('brace-whole', '手机', 'topic'),
      node('part-a', '处理器', 'brace'),
      node('sub-a1', '子部分1.1', 'brace'),
      node('sub-a2', '子部分1.2', 'brace'),
      node('part-b', '图像传感器', 'brace'),
      node('sub-b1', '镜头', 'brace'),
      node('sub-b2', '滤光片', 'brace'),
      node('sub-b3', '感光元件', 'brace'),
      node('sub-b4', '对焦马达', 'brace'),
      node('sub-b5', '防抖', 'brace'),
      node('sub-b6', '闪光灯', 'brace'),
    ]
    const connections: Connection[] = [
      edge('brace-whole', 'part-a'),
      edge('part-a', 'sub-a1'),
      edge('part-a', 'sub-a2'),
      edge('brace-whole', 'part-b'),
      edge('part-b', 'sub-b1'),
      edge('part-b', 'sub-b2'),
      edge('part-b', 'sub-b3'),
      edge('part-b', 'sub-b4'),
      edge('part-b', 'sub-b5'),
      edge('part-b', 'sub-b6'),
    ]

    const laidOut = recalculateBraceMapLayout(nodes, connections)
    const whole = positionOf(laidOut, 'brace-whole')
    const first = positionOf(laidOut, 'sub-a1')
    const last = positionOf(laidOut, 'sub-b6')
    const mid = (first.y + last.y) / 2
    expect(Math.abs(whole.y - mid)).toBeLessThan(40)
    expect(whole.y).toBeGreaterThan(first.y)
    expect(whole.y).toBeLessThan(last.y)
  })
})
