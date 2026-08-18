import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { Connection, DiagramNode } from '@/types'
import {
  distributeBranchesClockwise,
  loadMindMapSpec,
  mindMapBranchesClockwiseOrder,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { useUIStore } from '@/stores/ui'
import {
  buildMindMapOutlineTree,
  flattenMindMapOutline,
  mindMapOutlineOrderFingerprint,
} from '@/utils/mindMapOutlineTree'

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '../..')
const SAMS_L1_FIXTURE = join(REPO_ROOT, 'tests/fixtures/zhihui_sams_club_l1.json')

/** Real export order from 山姆会员商店_2026-08-07.mg */
const SAMS_CLUB_EXPECTED_L1 = [
  '竞争对手',
  '分布特点',
  '分部特',
  '产品与货品策略',
  '营销聚焦：目标客群与价值主张',
  '新分支',
  '运营与精益管理',
  '店内体验与多渠道',
  'Costco对比',
  '汇源汁商店',
]

function node(
  id: string,
  text: string,
  y: number,
  type: DiagramNode['type'] = 'branch',
  x = 0
): DiagramNode {
  return {
    id,
    text,
    type,
    position: { x, y },
  }
}

/** Build a laid-out topic + L1 branches matching distributeBranchesClockwise stacks. */
function diagramFromClockwiseLabels(labels: string[]): {
  nodes: DiagramNode[]
  connections: Connection[]
  clockwise: string[]
} {
  const branches = labels.map((text) => ({ text }))
  const { rightBranches, leftBranches } = distributeBranchesClockwise(branches)
  const nodes: DiagramNode[] = [node('topic', '中心', 100, 'topic')]
  const connections: Connection[] = []
  let edge = 0
  // stackBranches walks each side top→bottom in array order.
  rightBranches.forEach((branch, i) => {
    const id = `uid-r-${i}`
    nodes.push(node(id, branch.text, 40 + i * 80, 'branch', 200))
    connections.push({ id: `e${edge++}`, source: 'topic', target: id })
  })
  leftBranches.forEach((branch, i) => {
    const id = `uid-l-${i}`
    nodes.push(node(id, branch.text, 40 + i * 80, 'branch', -200))
    connections.push({ id: `e${edge++}`, source: 'topic', target: id })
  })
  return {
    nodes,
    connections,
    clockwise: mindMapBranchesClockwiseOrder(rightBranches, leftBranches).map((b) => b.text),
  }
}

describe('buildMindMapOutlineTree', () => {
  it('matches real 山姆会员商店 .mg L1 fixture clockwise order', () => {
    const spec = JSON.parse(readFileSync(SAMS_L1_FIXTURE, 'utf8')) as {
      nodes: DiagramNode[]
      connections: Connection[]
    }
    const flat = flattenMindMapOutline(
      buildMindMapOutlineTree(spec.nodes, spec.connections)
    )
    expect(flat[0]?.text).toBe('山姆会员商店')
    expect(flat.filter((row) => row.depth === 1).map((row) => row.text)).toEqual(
      SAMS_CLUB_EXPECTED_L1
    )
  })

  it('orders topic children clockwise: right top→bottom, left bottom→top', () => {
    const nodes: DiagramNode[] = [
      node('topic', '中心', 100, 'topic', 0),
      node('uid-rb', '右下', 200, 'branch', 200),
      node('uid-rt', '右上', 40, 'branch', 200),
      node('uid-lb', '左下', 220, 'branch', -200),
      node('uid-lt', '左上', 50, 'branch', -200),
    ]
    // Connection order intentionally inverted vs visual top→bottom.
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-rb' },
      { id: 'e2', source: 'topic', target: 'uid-rt' },
      { id: 'e3', source: 'topic', target: 'uid-lb' },
      { id: 'e4', source: 'topic', target: 'uid-lt' },
    ]

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '右上', '右下', '左下', '左上'])
  })

  it('matches Sam\'s Club style 8-branch clockwise reading order', () => {
    // Right top→bottom, then left bottom→top (connection order scrambled).
    const nodes: DiagramNode[] = [
      node('topic', '山姆会员商店', 400, 'topic', 0),
      node('uid-r0', '竞争对手', 80, 'branch', 320),
      node('uid-r1', '分布特点', 220, 'branch', 320),
      node('uid-r2', '产品与货品策略', 360, 'branch', 320),
      node('uid-r3', '营销聚焦', 500, 'branch', 320),
      node('uid-l0', '汇源汁商店', 80, 'branch', -320),
      node('uid-l1', 'Costco对比', 220, 'branch', -320),
      node('uid-l2', '店内体验与多渠道', 360, 'branch', -320),
      node('uid-l3', '运营与精益管理', 500, 'branch', -320),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-l2' },
      { id: 'e2', source: 'topic', target: 'uid-r3' },
      { id: 'e3', source: 'topic', target: 'uid-l0' },
      { id: 'e4', source: 'topic', target: 'uid-r0' },
      { id: 'e5', source: 'topic', target: 'uid-l3' },
      { id: 'e6', source: 'topic', target: 'uid-r1' },
      { id: 'e7', source: 'topic', target: 'uid-l1' },
      { id: 'e8', source: 'topic', target: 'uid-r2' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual([
      '山姆会员商店',
      '竞争对手',
      '分布特点',
      '产品与货品策略',
      '营销聚焦',
      '运营与精益管理',
      '店内体验与多渠道',
      'Costco对比',
      '汇源汁商店',
    ])
  })

  it('orders geometric 8-branch layout without branch-r/l prefixes', () => {
    const nodes: DiagramNode[] = [
      node('topic', '山姆会员商店', 400, 'topic', 0),
      node('r0', '竞争对手', 80, 'branch', 320),
      node('r1', '分布特点', 220, 'branch', 320),
      node('r2', '产品与货品策略', 360, 'branch', 320),
      node('r3', '营销聚焦', 500, 'branch', 320),
      node('l0', '汇源汁商店', 80, 'branch', -320),
      node('l1', 'Costco对比', 220, 'branch', -320),
      node('l2', '店内体验与多渠道', 360, 'branch', -320),
      node('l3', '运营与精益管理', 500, 'branch', -320),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'l3' },
      { id: 'e2', source: 'topic', target: 'r0' },
      { id: 'e3', source: 'topic', target: 'l0' },
      { id: 'e4', source: 'topic', target: 'r2' },
      { id: 'e5', source: 'topic', target: 'l1' },
      { id: 'e6', source: 'topic', target: 'r1' },
      { id: 'e7', source: 'topic', target: 'l2' },
      { id: 'e8', source: 'topic', target: 'r3' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.slice(1).map((r) => r.text)).toEqual([
      '竞争对手',
      '分布特点',
      '产品与货品策略',
      '营销聚焦',
      '运营与精益管理',
      '店内体验与多渠道',
      'Costco对比',
      '汇源汁商店',
    ])
  })

  it('treats x === topic.x as the right column', () => {
    const nodes: DiagramNode[] = [
      node('topic', '中心', 100, 'topic', 0),
      node('mid-top', '轴上上', 20, 'branch', 0),
      node('mid-bot', '轴上下', 180, 'branch', 0),
      node('left', '左侧', 100, 'branch', -100),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'left' },
      { id: 'e2', source: 'topic', target: 'mid-bot' },
      { id: 'e3', source: 'topic', target: 'mid-top' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '轴上上', '轴上下', '左侧'])
  })

  it('orders by geometric side without branch-r/l id prefixes', () => {
    const nodes: DiagramNode[] = [
      node('topic', '中心', 100, 'topic', 0),
      node('a', '右下', 200, 'branch', 200),
      node('b', '右上', 40, 'branch', 200),
      node('c', '左下', 220, 'branch', -200),
      node('d', '左上', 50, 'branch', -200),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'a' },
      { id: 'e2', source: 'topic', target: 'b' },
      { id: 'e3', source: 'topic', target: 'c' },
      { id: 'e4', source: 'topic', target: 'd' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '右上', '右下', '左下', '左上'])
  })

  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    'matches distributeBranchesClockwise reading order for %i L1 branches',
    (count) => {
      const labels = Array.from({ length: count }, (_, i) => String(i + 1))
      const { nodes, connections, clockwise } = diagramFromClockwiseLabels(labels)
      const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
      expect(flat.map((r) => r.text)).toEqual(['中心', ...clockwise])
      expect(clockwise).toEqual(labels)
    }
  )

  it('reverses left connection order when positions are missing (N=5)', () => {
    // Clockwise 1..5 → right [1,2,3], left stack top→bottom [5,4].
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '中心', type: 'topic' },
      { id: 'branch-r-1-0', text: '1', type: 'branch' },
      { id: 'branch-r-1-1', text: '2', type: 'branch' },
      { id: 'branch-r-1-2', text: '3', type: 'branch' },
      { id: 'branch-l-1-0', text: '5', type: 'branch' },
      { id: 'branch-l-1-1', text: '4', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-r-1-0' },
      { id: 'e2', source: 'topic', target: 'branch-r-1-1' },
      { id: 'e3', source: 'topic', target: 'branch-r-1-2' },
      { id: 'e4', source: 'topic', target: 'branch-l-1-0' },
      { id: 'e5', source: 'topic', target: 'branch-l-1-1' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '1', '2', '3', '4', '5'])
  })

  it('orders nested children top→bottom by Y', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'T', 100, 'topic', 0),
      node('uid-parent', 'Parent', 80, 'branch', 200),
      node('uid-child-b', 'ChildB', 160, 'branch', 280),
      node('uid-child-a', 'ChildA', 90, 'branch', 280),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-parent' },
      { id: 'e2', source: 'uid-parent', target: 'uid-child-b' },
      { id: 'e3', source: 'uid-parent', target: 'uid-child-a' },
    ]

    const parent = buildMindMapOutlineTree(nodes, connections)[0]?.children[0]
    expect(parent?.children.map((c) => c.text)).toEqual(['ChildA', 'ChildB'])
  })

  it('falls back to polar clockwise when not all children have positions', () => {
    // No branch-r/l prefixes; missing one position → polar (not side-split).
    const nodes: DiagramNode[] = [
      { id: 'topic', text: '中心', type: 'topic', position: { x: 0, y: 100 } },
      { id: 'up', text: '上', type: 'branch', position: { x: 0, y: 0 } },
      { id: 'right', text: '右', type: 'branch', position: { x: 200, y: 100 } },
      { id: 'down', text: '下', type: 'branch', position: { x: 0, y: 200 } },
      { id: 'left', text: '左', type: 'branch', position: { x: -200, y: 100 } },
      { id: 'orphan', text: '无坐标', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'down' },
      { id: 'e2', source: 'topic', target: 'left' },
      { id: 'e3', source: 'topic', target: 'up' },
      { id: 'e4', source: 'topic', target: 'right' },
      { id: 'e5', source: 'topic', target: 'orphan' },
    ]
    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['中心', '上', '右', '下', '左', '无坐标'])
  })

  it('falls back to connection order when positions are missing', () => {
    const nodes: DiagramNode[] = [
      { id: 'topic', text: 'T', type: 'topic' },
      { id: 'uid-first', text: 'First', type: 'branch' },
      { id: 'uid-second', text: 'Second', type: 'branch' },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-first' },
      { id: 'e2', source: 'topic', target: 'uid-second' },
    ]

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['T', 'First', 'Second'])
  })

  it('reflects live text labels from the diagram nodes', () => {
    const nodes: DiagramNode[] = [
      node('topic', 'Old topic', 0, 'topic'),
      node('uid-branch', 'Old branch', 40),
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'uid-branch' },
    ]

    nodes[0] = { ...nodes[0], text: 'New topic' }
    nodes[1] = { ...nodes[1], text: 'New branch' }

    const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
    expect(flat.map((r) => r.text)).toEqual(['New topic', 'New branch'])
  })
})

describe('buildMindMapOutlineTree vs loadMindMapSpec layouts', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(() => false),
      }))
    )
    useUIStore().mindMapCanvasMode = 'v2'
  })

  it.each([1, 2, 3, 4, 5, 6, 7, 8])(
    'follows layout clockwise order after loadMindMapSpec with %i branches',
    (count) => {
      const children = Array.from({ length: count }, (_, i) => ({ text: String(i + 1) }))
      const { nodes, connections } = loadMindMapSpec({ topic: '中心', children })
      const extracted = nodesAndConnectionsToMindMapSpec(nodes, connections)
      const clockwise = mindMapBranchesClockwiseOrder(
        extracted.rightBranches,
        extracted.leftBranches
      ).map((b) => b.text)

      const flat = flattenMindMapOutline(buildMindMapOutlineTree(nodes, connections))
      expect(flat.map((r) => r.text)).toEqual(['中心', ...clockwise])
      expect(clockwise).toEqual(children.map((c) => c.text))
    }
  )
})

describe('mindMapOutlineOrderFingerprint', () => {
  it('stays stable when Y nudges without changing sibling order', () => {
    const { nodes, connections } = diagramFromClockwiseLabels(['A', 'B', 'C', 'D'])
    const before = mindMapOutlineOrderFingerprint(nodes, connections)
    const nudged = nodes.map((item) =>
      item.id === 'topic'
        ? item
        : { ...item, position: { x: item.position?.x ?? 0, y: (item.position?.y ?? 0) + 0.4 } }
    )
    expect(mindMapOutlineOrderFingerprint(nudged, connections)).toBe(before)
  })
})
